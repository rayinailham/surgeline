"""Tes kontrak skema antrean P4 (D4, D5, D6, D8)."""

import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from src.schema import (
    ALLOWED_TRANSITIONS,
    ATTEMPT_OUTCOMES,
    JOB_STATUSES,
    RECORD_FIELDS,
    SCHEMA_VERSION,
    SchemaError,
    assert_transition,
    connect,
    init_db,
    is_valid_transition,
    status_counts,
)

PAYLOAD = json.dumps({field: "x" for field in RECORD_FIELDS})


def _insert(conn: sqlite3.Connection, verb: str, external_ref: str, **columns: object) -> int:
    now = time.time()
    values = {
        "external_ref": external_ref,
        "payload": PAYLOAD,
        "created_at": now,
        "updated_at": now,
        **columns,
    }
    names = ", ".join(values)
    holders = ", ".join(f":{name}" for name in values)
    return conn.execute(f"{verb} INTO jobs ({names}) VALUES ({holders})", values).rowcount


def insert_job(conn: sqlite3.Connection, external_ref: str, **columns: object) -> int:
    """`INSERT OR IGNORE` satu job seperti yang dilakukan loader P5 (D4)."""
    return _insert(conn, "INSERT OR IGNORE", external_ref, **columns)


def insert_job_strict(conn: sqlite3.Connection, external_ref: str, **columns: object) -> int:
    """`INSERT` biasa: dipakai untuk membuktikan constraint benar-benar menolak.

    `OR IGNORE` menelan semua pelanggaran constraint, bukan hanya duplikat, jadi
    constraint harus diuji lewat INSERT polos.
    """
    return _insert(conn, "INSERT", external_ref, **columns)


class SchemaTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.db_path = Path(self._tempdir.name) / "run" / "queue.db"
        self.conn = init_db(self.db_path)
        self.addCleanup(self.conn.close)


class TestInitDb(SchemaTestCase):
    def test_membuat_tabel_dan_indeks_kontrak(self) -> None:
        names = {
            row["name"]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
            )
        }
        self.assertIn("jobs", names)
        self.assertIn("attempts", names)
        self.assertIn("meta", names)
        self.assertIn("idx_jobs_status", names)
        self.assertIn("idx_jobs_status_claimed_at", names)
        self.assertIn("idx_jobs_status_updated_at", names)
        self.assertIn("idx_attempts_external_ref", names)

    def test_kolom_jobs_sesuai_docs_schema(self) -> None:
        columns = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(jobs)")
        }
        self.assertEqual(
            columns,
            {
                "external_ref",
                "payload",
                "status",
                "attempts",
                "worker_id",
                "claimed_at",
                "confirmation",
                "last_error",
                "created_at",
                "updated_at",
            },
        )

    def test_wal_dan_busy_timeout_aktif(self) -> None:
        """D5: tanpa WAL, N worker menulis akan saling-blok parah."""
        mode = self.conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode.lower(), "wal")
        self.assertEqual(self.conn.execute("PRAGMA busy_timeout").fetchone()[0], 5000)
        self.assertEqual(self.conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_wal_persisten_untuk_koneksi_proses_lain(self) -> None:
        """Worker/dashboard yang membuka DB yang sudah ada tetap dapat WAL."""
        other = connect(self.db_path)
        self.addCleanup(other.close)
        mode = other.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode.lower(), "wal")
        self.assertEqual(other.execute("PRAGMA busy_timeout").fetchone()[0], 5000)

    def test_idempoten_dan_tidak_menghapus_data(self) -> None:
        """Resume (P9) memanggil init_db pada DB terisi."""
        insert_job(self.conn, "REC-000001")
        again = init_db(self.db_path)
        self.addCleanup(again.close)
        self.assertEqual(
            again.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 1
        )
        version = again.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()[0]
        self.assertEqual(int(version), SCHEMA_VERSION)

    def test_schema_version_beda_ditolak(self) -> None:
        self.conn.execute("UPDATE meta SET value = '99' WHERE key = 'schema_version'")
        with self.assertRaises(SchemaError):
            init_db(self.db_path).close()

    def test_default_job_baru_pending_tanpa_percobaan(self) -> None:
        insert_job(self.conn, "REC-000001")
        row = self.conn.execute(
            "SELECT status, attempts, worker_id, claimed_at, confirmation, last_error "
            "FROM jobs WHERE external_ref = 'REC-000001'"
        ).fetchone()
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["attempts"], 0)
        self.assertIsNone(row["worker_id"])
        self.assertIsNone(row["claimed_at"])
        self.assertIsNone(row["confirmation"])
        self.assertIsNone(row["last_error"])


class TestDedup(SchemaTestCase):
    def test_insert_or_ignore_external_ref_sama_dua_kali_tetap_satu_baris(self) -> None:
        """D4: duplikat ditolak DB, bukan dicek di memori proses."""
        self.assertEqual(insert_job(self.conn, "REC-000001"), 1)
        self.assertEqual(insert_job(self.conn, "REC-000001"), 0)

        total, distinct = self.conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT external_ref) FROM jobs"
        ).fetchone()
        self.assertEqual(total, 1)
        self.assertEqual(total - distinct, 0)

    def test_muat_ulang_penuh_tidak_menambah_duplikat(self) -> None:
        """Load ulang / resume tidak boleh menggandakan antrean."""
        refs = [f"REC-{index:06d}" for index in range(1, 21)]
        for ref in refs + refs:
            insert_job(self.conn, ref)
        total, distinct = self.conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT external_ref) FROM jobs"
        ).fetchone()
        self.assertEqual((total, distinct), (20, 20))

    def test_insert_or_ignore_tidak_menimpa_progres_job(self) -> None:
        """Muat ulang di tengah run tidak boleh mengembalikan job 'ok' jadi 'pending'."""
        insert_job(self.conn, "REC-000001")
        self.conn.execute(
            "UPDATE jobs SET status = 'ok', confirmation = 'SL-abcd1234' "
            "WHERE external_ref = 'REC-000001'"
        )
        insert_job(self.conn, "REC-000001")
        row = self.conn.execute(
            "SELECT status, confirmation FROM jobs WHERE external_ref = 'REC-000001'"
        ).fetchone()
        self.assertEqual((row["status"], row["confirmation"]), ("ok", "SL-abcd1234"))

    def test_external_ref_null_ditolak(self) -> None:
        """PRIMARY KEY TEXT di SQLite mengizinkan NULL; NOT NULL menutup celah itu."""
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO jobs (external_ref, payload, created_at, updated_at) "
                "VALUES (NULL, ?, ?, ?)",
                (PAYLOAD, time.time(), time.time()),
            )


class TestConfirmation(SchemaTestCase):
    def test_konfirmasi_dobel_non_null_ditolak(self) -> None:
        """D6: satu external_ref -> paling banyak satu nomor konfirmasi, dan sebaliknya."""
        insert_job_strict(self.conn, "REC-000001", status="ok", confirmation="SL-abcd1234")
        with self.assertRaises(sqlite3.IntegrityError):
            insert_job_strict(self.conn, "REC-000002", status="ok", confirmation="SL-abcd1234")

    def test_banyak_konfirmasi_null_diizinkan(self) -> None:
        """Job pending belum punya konfirmasi; UNIQUE SQLite mengizinkan banyak NULL."""
        for index in range(1, 6):
            insert_job(self.conn, f"REC-{index:06d}")
        pending = self.conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE confirmation IS NULL"
        ).fetchone()[0]
        self.assertEqual(pending, 5)


class TestConstraints(SchemaTestCase):
    def test_status_di_luar_state_machine_ditolak(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            insert_job_strict(self.conn, "REC-000001", status="selesai")

    def test_attempts_negatif_ditolak(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            insert_job_strict(self.conn, "REC-000001", attempts=-1)

    def test_outcome_attempts_di_luar_kontrak_ditolak(self) -> None:
        insert_job(self.conn, "REC-000001")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO attempts (external_ref, worker_id, started_at, outcome) "
                "VALUES ('REC-000001', 'w1', ?, 'entahlah')",
                (time.time(),),
            )

    def test_attempts_wajib_menunjuk_job_yang_ada(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO attempts (external_ref, worker_id, started_at, outcome) "
                "VALUES ('REC-hantu', 'w1', ?, 'ok')",
                (time.time(),),
            )

    def test_or_ignore_menelan_pelanggaran_constraint_bukan_hanya_duplikat(self) -> None:
        """Peringatan kontrak untuk loader P5.

        `INSERT OR IGNORE` mendiamkan CHECK dan UNIQUE apa pun, bukan hanya bentrok
        `external_ref`. Loader wajib memvalidasi record sebelum insert dan memakai
        `rowcount` untuk membedakan "dilewati" dari "masuk"; kalau tidak, record cacat
        hilang tanpa jejak dan hitungan dedup jadi bohong.
        """
        self.assertEqual(insert_job(self.conn, "REC-000001", status="selesai"), 0)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 0
        )

    def test_audit_percobaan_merekam_tiap_mode_chaos(self) -> None:
        """docs/CHAOS.md: 500 -> retryable, slow -> timeout, validasi -> permanent."""
        insert_job(self.conn, "REC-000001", attempts=4)
        for outcome in sorted(ATTEMPT_OUTCOMES):
            self.conn.execute(
                "INSERT INTO attempts "
                "(external_ref, worker_id, started_at, ended_at, outcome) "
                "VALUES ('REC-000001', 'w1', ?, ?, ?)",
                (time.time(), time.time(), outcome),
            )
        recorded = {
            row["outcome"]
            for row in self.conn.execute("SELECT outcome FROM attempts")
        }
        self.assertEqual(recorded, set(ATTEMPT_OUTCOMES))


class TestStateMachine(unittest.TestCase):
    def test_peta_transisi_hanya_memakai_status_sah(self) -> None:
        self.assertEqual(set(ALLOWED_TRANSITIONS), set(JOB_STATUSES))
        for current, targets in ALLOWED_TRANSITIONS.items():
            with self.subTest(status=current):
                self.assertTrue(targets <= JOB_STATUSES)

    def test_transisi_sah_diterima(self) -> None:
        for current, new in (
            ("pending", "claimed"),
            ("claimed", "ok"),
            ("claimed", "failed"),
            ("claimed", "pending"),  # retry / lease kedaluwarsa (D8)
            ("claimed", "dead"),
            ("pending", "dead"),
        ):
            with self.subTest(transition=f"{current}->{new}"):
                self.assertTrue(is_valid_transition(current, new))
                assert_transition(current, new)

    def test_transisi_ilegal_ditolak(self) -> None:
        for current, new in (
            ("pending", "ok"),  # sukses wajib lewat claimed
            ("ok", "pending"),  # status akhir tidak dibuka ulang
            ("failed", "claimed"),
            ("dead", "ok"),
            ("claimed", "claimed"),  # cegah double-claim (P7)
        ):
            with self.subTest(transition=f"{current}->{new}"):
                self.assertFalse(is_valid_transition(current, new))
                with self.assertRaises(SchemaError):
                    assert_transition(current, new)

    def test_status_tak_dikenal_menaikkan_schema_error(self) -> None:
        with self.assertRaises(SchemaError):
            assert_transition("pending", "selesai")
        with self.assertRaises(SchemaError):
            assert_transition("selesai", "ok")


class TestStatusCounts(SchemaTestCase):
    def test_semua_status_muncul_walau_nol(self) -> None:
        insert_job(self.conn, "REC-000001")
        insert_job(self.conn, "REC-000002", status="ok", confirmation="SL-00000001")
        counts = status_counts(self.conn)
        self.assertEqual(set(counts), set(JOB_STATUSES))
        self.assertEqual(counts["pending"], 1)
        self.assertEqual(counts["ok"], 1)
        self.assertEqual(counts["dead"], 0)
        self.assertEqual(
            sum(counts.values()),
            self.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
        )


if __name__ == "__main__":
    unittest.main()
