"""Worker + store tests. HTML fixtures only — no network, no browser (P6 DoD)."""

import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from src import store
from src.schema import SchemaError, init_db
from src.worker import (
    SubmitResult,
    WorkerError,
    _apply,
    _assert_local_target,
    _field_text,
    classify_response,
    parse_result_page,
)

# Ditangkap dari target `:8110` yang sesungguhnya (P6), bukan markup karangan:
# kalau target berubah bentuk, fixture ini yang harus diperbarui bersama worker.
PAGE_HEAD = (
    '<!doctype html>\n<html lang="id"><head><meta charset="utf-8">\n'
    "<title>{title}</title>\n</head><body>\n<h1>{title}</h1>\n"
)
RESULT_OK = PAGE_HEAD.format(title="Pengajuan Diterima") + (
    '<div class="ok" id="result" data-created="1">'
    "<p>Pengajuan diterima. Simpan nomor konfirmasi berikut:</p>"
    '<div id="confirmation" data-confirmation="SL-a6d5ec39">SL-a6d5ec39</div>'
    '<p>Referensi: <span id="echo-external-ref">FIXTURE-OK-1</span></p></div>'
    '<p><a id="back" href="/">Kirim pengajuan lain</a></p>\n</body></html>\n'
)
RESULT_VALIDATION = PAGE_HEAD.format(title="Formulir Pengajuan Klaim") + (
    '<div class="err" id="error" data-error="validation">'
    "<strong>Pengajuan ditolak validasi.</strong>"
    '<ul id="error-list"><li>full_name wajib diisi</li>'
    "<li>email tidak berformat alamat email yang sah</li>"
    "<li>amount harus lebih besar dari 0</li></ul></div>\n"
    '<form id="submission-form" method="post" action="/submit">'
    '<input id="external_ref" name="external_ref" type="text" required>'
    '<button id="submit-btn" type="submit">Kirim</button></form>\n</body></html>\n'
)
RESULT_CHAOS_VALIDATION = PAGE_HEAD.format(title="Formulir Pengajuan Klaim") + (
    '<div class="err" id="error" data-error="validation">'
    '<ul id="error-list"><li>record ditolak oleh chaos target</li></ul></div>\n'
    "</body></html>\n"
)
RESULT_SERVER_ERROR = PAGE_HEAD.format(title="Gangguan Server") + (
    '<div class="err" id="error">Gangguan server sementara.</div>\n</body></html>\n'
)
# Halaman 200 yang "terlihat sukses" tapi nomor konfirmasinya hilang (D6).
RESULT_OK_TANPA_KONFIRMASI = PAGE_HEAD.format(title="Pengajuan Diterima") + (
    '<div class="ok" id="result" data-created="1"><p>Pengajuan diterima.</p></div>\n'
    "</body></html>\n"
)


def record(external_ref: str = "REC-001") -> dict[str, object]:
    return {
        "external_ref": external_ref,
        "full_name": "Budi Saputra",
        "email": "budi@example.org",
        "policy_no": "POL-0001",
        "amount": 125000.5,
        "notes": "Data sintetis.",
    }


class TestHalamanHasil(unittest.TestCase):
    def test_konfirmasi_terbaca_dari_halaman_sukses(self) -> None:
        confirmation, errors = parse_result_page(RESULT_OK)
        self.assertEqual((confirmation, errors), ("SL-a6d5ec39", []))

    def test_pesan_validasi_terbaca_semua(self) -> None:
        confirmation, errors = parse_result_page(RESULT_VALIDATION)
        self.assertIsNone(confirmation)
        self.assertEqual(
            errors,
            [
                "full_name wajib diisi",
                "email tidak berformat alamat email yang sah",
                "amount harus lebih besar dari 0",
            ],
        )

    def test_konfirmasi_berbentuk_asing_diperlakukan_hilang(self) -> None:
        aneh = RESULT_OK.replace("SL-a6d5ec39", "MENUNGGU")
        self.assertIsNone(parse_result_page(aneh)[0])


class TestKlasifikasi(unittest.TestCase):
    def test_200_dengan_konfirmasi_ok(self) -> None:
        self.assertEqual(
            classify_response(200, RESULT_OK),
            SubmitResult(outcome="ok", confirmation="SL-a6d5ec39"),
        )

    def test_200_tanpa_konfirmasi_dihitung_gagal_permanen(self) -> None:
        result = classify_response(200, RESULT_OK_TANPA_KONFIRMASI)
        self.assertEqual(result.outcome, "permanent")
        self.assertIsNone(result.confirmation)
        self.assertIn("tanpa nomor konfirmasi", result.error or "")

    def test_500_retryable(self) -> None:
        result = classify_response(500, RESULT_SERVER_ERROR)
        self.assertEqual((result.outcome, result.confirmation), ("retryable", None))

    def test_429_dan_503_retryable(self) -> None:
        for status in (429, 503):
            with self.subTest(status=status):
                self.assertEqual(classify_response(status, "").outcome, "retryable")

    def test_422_permanen_dengan_alasan(self) -> None:
        result = classify_response(422, RESULT_CHAOS_VALIDATION)
        self.assertEqual(result.outcome, "permanent")
        self.assertEqual(result.error, "HTTP 422: record ditolak oleh chaos target")

    def test_status_tak_diharapkan_permanen(self) -> None:
        self.assertEqual(classify_response(404, "").outcome, "permanent")


class TestBatasEtika(unittest.TestCase):
    def test_target_lokal_diterima(self) -> None:
        for url in ("http://127.0.0.1:8110", "http://localhost:8111"):
            with self.subTest(url=url):
                _assert_local_target(url)

    def test_target_pihak_lain_ditolak(self) -> None:
        for url in ("https://contoh-orang-lain.co.id", "http://10.0.0.5:8110", "file:///etc"):
            with self.subTest(url=url):
                with self.assertRaisesRegex(WorkerError, "harus lokal"):
                    _assert_local_target(url)


class TestFieldForm(unittest.TestCase):
    def test_amount_tidak_pernah_notasi_ilmiah(self) -> None:
        self.assertEqual(_field_text("amount", 1e21), "1000000000000000000000.00")

    def test_notes_kosong_jadi_string_kosong(self) -> None:
        self.assertEqual(_field_text("notes", None), "")


class StoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "run" / "queue.db"
        self.conn = init_db(self.db)
        self.addCleanup(self.conn.close)

    def seed(self, *refs: str) -> None:
        now = time.time()
        for ref in refs:
            self.conn.execute(
                "INSERT INTO jobs (external_ref, payload, status, created_at, updated_at)"
                " VALUES (?, ?, 'pending', ?, ?)",
                (ref, json.dumps(record(ref)), now, now),
            )

    def job_row(self, ref: str) -> sqlite3.Row:
        return self.conn.execute(
            "SELECT * FROM jobs WHERE external_ref = ?", (ref,)
        ).fetchone()

    def attempt_rows(self, ref: str) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM attempts WHERE external_ref = ? ORDER BY id", (ref,)
            )
        )


class TestStore(StoreTestCase):
    def test_claim_menandai_claimed_dan_menaikkan_attempts(self) -> None:
        self.seed("REC-001")
        job = store.claim_one(self.conn, "w-1")
        self.assertIsNotNone(job)
        assert job is not None
        row = self.job_row("REC-001")
        self.assertEqual(
            (row["status"], row["worker_id"], row["attempts"]), ("claimed", "w-1", 1)
        )
        self.assertIsNotNone(row["claimed_at"])
        self.assertEqual(job.payload, record("REC-001"))

    def test_dua_klaim_tidak_pernah_dapat_job_sama(self) -> None:
        self.seed("REC-001", "REC-002")
        first = store.claim_one(self.conn, "w-1")
        second = store.claim_one(self.conn, "w-2")
        assert first is not None and second is not None
        self.assertNotEqual(first.external_ref, second.external_ref)
        self.assertIsNone(store.claim_one(self.conn, "w-3"))

    def test_job_yang_dilepas_pindah_ke_belakang_antrean(self) -> None:
        # Regresi P6: dengan urutan `rowid`, job gagal ini langsung diklaim ulang dan
        # memakan seluruh run (terukur: 24 percobaan berturut-turut, 23 job tak tersentuh).
        self.seed("REC-001", "REC-002")
        first = store.claim_one(self.conn, "w-1")
        assert first is not None and first.external_ref == "REC-001"
        store.release(
            self.conn, "REC-001", "HTTP 500 dari target", worker_id="w-1", started_at=first.claimed_at
        )
        second = store.claim_one(self.conn, "w-1")
        assert second is not None
        self.assertEqual(second.external_ref, "REC-002")

    def test_mark_ok_menyimpan_konfirmasi_dan_baris_audit(self) -> None:
        self.seed("REC-001")
        job = store.claim_one(self.conn, "w-1")
        assert job is not None
        store.mark_ok(
            self.conn, "REC-001", "SL-a6d5ec39", worker_id="w-1", started_at=job.claimed_at
        )
        row = self.job_row("REC-001")
        self.assertEqual((row["status"], row["confirmation"]), ("ok", "SL-a6d5ec39"))
        self.assertIsNone(row["worker_id"])
        self.assertIsNone(row["claimed_at"])
        attempts = self.attempt_rows("REC-001")
        self.assertEqual(len(attempts), 1)
        self.assertEqual(
            (attempts[0]["outcome"], attempts[0]["confirmation"]), ("ok", "SL-a6d5ec39")
        )

    def test_mark_ok_tanpa_konfirmasi_ditolak_dan_job_tetap_claimed(self) -> None:
        self.seed("REC-001")
        job = store.claim_one(self.conn, "w-1")
        assert job is not None
        for kosong in ("", "   "):
            with self.subTest(konfirmasi=kosong):
                with self.assertRaisesRegex(store.StoreError, "tanpa nomor konfirmasi"):
                    store.mark_ok(
                        self.conn, "REC-001", kosong, worker_id="w-1", started_at=job.claimed_at
                    )
        self.assertEqual(self.job_row("REC-001")["status"], "claimed")
        self.assertEqual(self.attempt_rows("REC-001"), [])

    def test_mark_failed_menyimpan_alasan(self) -> None:
        self.seed("REC-001")
        job = store.claim_one(self.conn, "w-1")
        assert job is not None
        store.mark_failed(
            self.conn, "REC-001", "HTTP 422: ditolak", worker_id="w-1", started_at=job.claimed_at
        )
        row = self.job_row("REC-001")
        self.assertEqual((row["status"], row["last_error"]), ("failed", "HTTP 422: ditolak"))
        self.assertEqual(self.attempt_rows("REC-001")[0]["outcome"], "permanent")

    def test_release_mengembalikan_ke_pending_dan_membersihkan_lease(self) -> None:
        self.seed("REC-001")
        job = store.claim_one(self.conn, "w-1")
        assert job is not None
        store.release(
            self.conn,
            "REC-001",
            "HTTP 500 dari target",
            worker_id="w-1",
            started_at=job.claimed_at,
        )
        row = self.job_row("REC-001")
        self.assertEqual(row["status"], "pending")
        self.assertIsNone(row["worker_id"])
        self.assertIsNone(row["claimed_at"])
        # attempts tidak dikembalikan: percobaan gagal tetap terpakai (dasar D7).
        self.assertEqual(row["attempts"], 1)
        self.assertEqual(self.attempt_rows("REC-001")[0]["outcome"], "retryable")

    def test_release_timeout_tercatat_sebagai_timeout(self) -> None:
        self.seed("REC-001")
        job = store.claim_one(self.conn, "w-1")
        assert job is not None
        store.release(
            self.conn,
            "REC-001",
            "timeout 1500 ms",
            worker_id="w-1",
            started_at=job.claimed_at,
            outcome="timeout",
        )
        self.assertEqual(self.attempt_rows("REC-001")[0]["outcome"], "timeout")

    def test_worker_lain_tidak_bisa_menutup_job_yang_bukan_miliknya(self) -> None:
        self.seed("REC-001")
        job = store.claim_one(self.conn, "w-1")
        assert job is not None
        with self.assertRaisesRegex(store.StoreError, "dipegang 'w-1'"):
            store.mark_ok(
                self.conn, "REC-001", "SL-a6d5ec39", worker_id="w-2", started_at=job.claimed_at
            )
        self.assertEqual(self.job_row("REC-001")["status"], "claimed")

    def test_job_terminal_menolak_transisi_lanjutan(self) -> None:
        self.seed("REC-001")
        job = store.claim_one(self.conn, "w-1")
        assert job is not None
        store.mark_ok(
            self.conn, "REC-001", "SL-a6d5ec39", worker_id="w-1", started_at=job.claimed_at
        )
        with self.assertRaisesRegex(SchemaError, "transisi ilegal: ok -> failed"):
            store.mark_failed(
                self.conn, "REC-001", "telat", worker_id="w-1", started_at=job.claimed_at
            )

    def test_counts_dan_attempt_counts(self) -> None:
        self.seed("REC-001", "REC-002")
        job = store.claim_one(self.conn, "w-1")
        assert job is not None
        store.mark_ok(
            self.conn, "REC-001", "SL-a6d5ec39", worker_id="w-1", started_at=job.claimed_at
        )
        self.assertEqual(
            store.counts(self.conn),
            {"claimed": 0, "dead": 0, "failed": 0, "ok": 1, "pending": 1},
        )
        self.assertEqual(store.attempt_counts(self.conn), {"ok": 1})

    def test_dua_job_tidak_boleh_menyimpan_konfirmasi_sama(self) -> None:
        self.seed("REC-001", "REC-002")
        for ref in ("REC-001", "REC-002"):
            job = store.claim_one(self.conn, "w-1")
            assert job is not None and job.external_ref == ref
            if ref == "REC-001":
                store.mark_ok(
                    self.conn, ref, "SL-a6d5ec39", worker_id="w-1", started_at=job.claimed_at
                )
                continue
            with self.assertRaises(sqlite3.IntegrityError):
                store.mark_ok(
                    self.conn, ref, "SL-a6d5ec39", worker_id="w-1", started_at=job.claimed_at
                )
        self.assertEqual(self.job_row("REC-002")["status"], "claimed")


class TestPenerapanHasil(StoreTestCase):
    """`_apply` adalah satu-satunya jembatan hasil browser -> antrean."""

    def apply(self, result: SubmitResult) -> sqlite3.Row:
        self.seed("REC-001")
        job = store.claim_one(self.conn, "w-1")
        assert job is not None
        _apply(self.conn, job, result, job.claimed_at)
        return self.job_row("REC-001")

    def test_ok_masuk_dengan_konfirmasi(self) -> None:
        row = self.apply(SubmitResult(outcome="ok", confirmation="SL-a6d5ec39"))
        self.assertEqual((row["status"], row["confirmation"]), ("ok", "SL-a6d5ec39"))

    def test_retryable_kembali_pending(self) -> None:
        row = self.apply(SubmitResult(outcome="retryable", error="HTTP 500 dari target"))
        self.assertEqual((row["status"], row["last_error"]), ("pending", "HTTP 500 dari target"))

    def test_timeout_kembali_pending(self) -> None:
        row = self.apply(SubmitResult(outcome="timeout", error="timeout 1500 ms"))
        self.assertEqual(row["status"], "pending")

    def test_permanent_jadi_failed(self) -> None:
        row = self.apply(SubmitResult(outcome="permanent", error="HTTP 422: ditolak"))
        self.assertEqual((row["status"], row["last_error"]), ("failed", "HTTP 422: ditolak"))

    def test_ok_tanpa_konfirmasi_tidak_pernah_jadi_ok(self) -> None:
        # Pengaman lapis kedua: walau pemanggil salah menandai outcome `ok`,
        # tanpa nomor konfirmasi job tetap tidak boleh berstatus `ok` (D6).
        row = self.apply(SubmitResult(outcome="ok", confirmation=None))
        self.assertEqual(row["status"], "failed")


if __name__ == "__main__":
    unittest.main()
