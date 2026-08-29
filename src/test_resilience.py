"""Ketahanan P8: backoff, dead-letter, dan pemulihan lease. Tanpa browser, tanpa jaringan.

Semua waktu disuntik lewat parameter `now=` supaya test tidak pernah benar-benar tidur
dan tidak bisa berkedip (flaky) karena mesin sedang sibuk.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from src import store, worker
from src.schema import (
    BACKOFF_BASE_SECONDS,
    BACKOFF_CAP_SECONDS,
    BACKOFF_FACTOR,
    MAX_ATTEMPTS,
    backoff_delay,
    init_db,
)

NOW = 1_000_000.0


class _FakeClock:
    """Jam monotonic palsu: tiap pembacaan maju `step` detik."""

    def __init__(self, *, step: float) -> None:
        self.step = step
        self.now = 0.0

    def __call__(self) -> float:
        value = self.now
        self.now += self.step
        return value


def _no_sleep(_seconds: float) -> None:
    raise AssertionError("putaran tidak boleh benar-benar tidur di dalam test")


def _always_ok(payload: dict[str, str]) -> worker.SubmitResult:
    """Submit palsu yang selalu sukses dengan konfirmasi unik per `external_ref`."""
    digest = hashlib.sha256(payload["external_ref"].encode()).hexdigest()[:8]
    return worker.SubmitResult(outcome="ok", confirmation=f"SL-{digest}")


class ResilienceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.conn = init_db(Path(self.directory.name) / "queue.db")
        self.addCleanup(self.conn.close)

    def seed(self, *refs: str, created_at: float = NOW) -> None:
        self.conn.executemany(
            "INSERT INTO jobs (external_ref, payload, created_at, updated_at)"
            " VALUES (?, ?, ?, ?)",
            (
                (ref, json.dumps({"external_ref": ref}), created_at, created_at)
                for ref in refs
            ),
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

    def burn(self, ref: str, times: int, *, at: float = NOW) -> str:
        """Habiskan `times` percobaan retryable pada satu job; kembalikan status akhir."""
        status = "pending"
        for index in range(times):
            # Jauh melampaui backoff terpanjang supaya klaim tidak pernah tertahan.
            stamp = at + index * (BACKOFF_CAP_SECONDS + 60.0)
            job = store.claim_one(self.conn, "w-1", now=stamp)
            assert job is not None, f"job {ref!r} tidak bisa diklaim pada percobaan {index}"
            status = store.release(
                self.conn,
                ref,
                "HTTP 500 dari target",
                worker_id="w-1",
                started_at=stamp,
                now=stamp + 0.5,
            )
        return status


class TestBackoff(ResilienceTestCase):
    def test_backoff_naik_per_percobaan_lalu_berhenti_di_atap(self) -> None:
        self.assertEqual(backoff_delay(0), 0.0)
        self.assertEqual(backoff_delay(1), BACKOFF_BASE_SECONDS)
        self.assertEqual(backoff_delay(2), BACKOFF_BASE_SECONDS * BACKOFF_FACTOR)
        for step in range(1, 12):
            self.assertLessEqual(backoff_delay(step), BACKOFF_CAP_SECONDS)
            self.assertGreaterEqual(backoff_delay(step + 1), backoff_delay(step))
        self.assertEqual(backoff_delay(99), BACKOFF_CAP_SECONDS)

    def test_job_yang_baru_dilepas_belum_layak_diklaim(self) -> None:
        self.seed("REC-001")
        job = store.claim_one(self.conn, "w-1", now=NOW)
        assert job is not None
        store.release(
            self.conn, "REC-001", "HTTP 500 dari target", worker_id="w-1",
            started_at=NOW, now=NOW,
        )
        self.assertEqual(self.job_row("REC-001")["status"], "pending")
        # Backoff percobaan pertama = 1 dtk (+ jitter <= 25%); sedetik sesudahnya
        # job itu masih ada di antrean tapi belum boleh diambil siapa pun.
        self.assertIsNone(store.claim_one(self.conn, "w-2", now=NOW + 0.5))
        self.assertIsNotNone(store.claim_one(self.conn, "w-2", now=NOW + 2.0))

    def test_backoff_tidak_menahan_job_yang_belum_pernah_dicoba(self) -> None:
        self.seed("REC-001")
        self.assertIsNotNone(store.claim_one(self.conn, "w-1", now=NOW))

    def test_job_tertahan_backoff_tidak_menghalangi_job_lain(self) -> None:
        # Kalau backoff dilaksanakan dengan "kembalikan None", satu job yang menunggu
        # akan membekukan seluruh antrean. Yang benar: job itu dilewati.
        self.seed("REC-001", "REC-002")
        job = store.claim_one(self.conn, "w-1", now=NOW)
        assert job is not None and job.external_ref == "REC-001"
        store.release(
            self.conn, "REC-001", "HTTP 500", worker_id="w-1", started_at=NOW, now=NOW
        )
        second = store.claim_one(self.conn, "w-2", now=NOW + 0.1)
        assert second is not None
        self.assertEqual(second.external_ref, "REC-002")

    def test_time_until_ready_membedakan_antrean_habis_dari_antrean_menunggu(self) -> None:
        self.seed("REC-001")
        self.assertEqual(store.time_until_ready(self.conn, now=NOW), 0.0)
        job = store.claim_one(self.conn, "w-1", now=NOW)
        assert job is not None
        # Semua job sedang `claimed`: tidak ada baris `pending` sama sekali.
        self.assertIsNone(store.time_until_ready(self.conn, now=NOW))
        store.release(
            self.conn, "REC-001", "HTTP 500", worker_id="w-1", started_at=NOW, now=NOW
        )
        waiting = store.time_until_ready(self.conn, now=NOW)
        assert waiting is not None
        self.assertGreaterEqual(waiting, BACKOFF_BASE_SECONDS)
        self.assertEqual(store.time_until_ready(self.conn, now=NOW + 60.0), 0.0)


class TestDeadLetter(ResilienceTestCase):
    def test_percobaan_habis_masuk_dead_dengan_last_error(self) -> None:
        self.seed("REC-001")
        status = self.burn("REC-001", MAX_ATTEMPTS)
        self.assertEqual(status, "dead")
        row = self.job_row("REC-001")
        self.assertEqual((row["status"], row["attempts"]), ("dead", MAX_ATTEMPTS))
        self.assertIsNotNone(row["last_error"])
        self.assertIn("habis", row["last_error"])
        self.assertIn("HTTP 500 dari target", row["last_error"])
        # Baris audit terakhir tetap dicatat `retryable`: yang habis adalah jatah job,
        # bukan sifat kegagalannya.
        self.assertEqual([r["outcome"] for r in self.attempt_rows("REC-001")],
                         ["retryable"] * MAX_ATTEMPTS)

    def test_dead_adalah_terminal_dan_tidak_pernah_diklaim_lagi(self) -> None:
        self.seed("REC-001")
        self.burn("REC-001", MAX_ATTEMPTS)
        self.assertIsNone(store.claim_one(self.conn, "w-2", now=NOW + 100_000.0))

    def test_job_belum_habis_kembali_ke_pending_bukan_dead(self) -> None:
        self.seed("REC-001")
        self.assertEqual(self.burn("REC-001", MAX_ATTEMPTS - 1), "pending")
        self.assertEqual(self.job_row("REC-001")["status"], "pending")

    def test_penolakan_permanen_tidak_pernah_di_retry(self) -> None:
        self.seed("REC-001")
        job = store.claim_one(self.conn, "w-1", now=NOW)
        assert job is not None
        store.mark_failed(
            self.conn, "REC-001", "HTTP 422: record ditolak oleh chaos target",
            worker_id="w-1", started_at=NOW, now=NOW,
        )
        row = self.job_row("REC-001")
        self.assertEqual((row["status"], row["attempts"]), ("failed", 1))
        self.assertIn("422", row["last_error"])
        # Tidak ada backoff, tidak ada percobaan kedua: 422 bukan gangguan sementara.
        self.assertIsNone(store.claim_one(self.conn, "w-2", now=NOW + 100_000.0))
        self.assertEqual([r["outcome"] for r in self.attempt_rows("REC-001")], ["permanent"])


class TestLeaseRecovery(ResilienceTestCase):
    def test_hanya_job_yang_melewati_lease_yang_ditarik(self) -> None:
        self.seed("REC-STALE", "REC-FRESH")
        stale = store.claim_one(self.conn, "w-mati", now=NOW)
        fresh = store.claim_one(self.conn, "w-hidup", now=NOW + 100.0)
        assert stale is not None and fresh is not None
        self.assertEqual(stale.external_ref, "REC-STALE")

        recovered = store.recover_stuck(
            self.conn, lease_timeout=60.0, now=NOW + 120.0
        )
        self.assertEqual(recovered, {"pending": 1, "dead": 0})
        self.assertEqual(self.job_row("REC-STALE")["status"], "pending")
        stale_row = self.job_row("REC-STALE")
        self.assertIsNone(stale_row["worker_id"])
        self.assertIsNone(stale_row["claimed_at"])
        self.assertIn("lease", stale_row["last_error"])
        # Job yang masih dikerjakan worker hidup tidak boleh direbut: itu jalan
        # menuju dua worker mengisi form yang sama.
        fresh_row = self.job_row("REC-FRESH")
        self.assertEqual((fresh_row["status"], fresh_row["worker_id"]), ("claimed", "w-hidup"))

    def test_recovery_tidak_menaikkan_attempts_dua_kali(self) -> None:
        # `claim_one` sudah memakai satu jatah saat job diklaim; kalau sapuan lease
        # menaikkannya lagi, satu percobaan dihukum dua kali dan job beracun mati
        # lebih cepat dari `max_attempts`.
        self.seed("REC-001")
        store.claim_one(self.conn, "w-mati", now=NOW)
        self.assertEqual(self.job_row("REC-001")["attempts"], 1)
        store.recover_stuck(self.conn, lease_timeout=60.0, now=NOW + 120.0)
        self.assertEqual(self.job_row("REC-001")["attempts"], 1)

    def test_recovery_menutup_baris_audit_percobaan_yang_ditinggal_mati(self) -> None:
        self.seed("REC-001")
        store.claim_one(self.conn, "w-mati", now=NOW)
        self.assertEqual(self.attempt_rows("REC-001"), [])
        store.recover_stuck(self.conn, lease_timeout=60.0, now=NOW + 120.0)
        rows = self.attempt_rows("REC-001")
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["outcome"], rows[0]["worker_id"]), ("timeout", "w-mati"))
        self.assertEqual((rows[0]["started_at"], rows[0]["ended_at"]), (NOW, NOW + 120.0))

    def test_job_yatim_yang_jatahnya_habis_masuk_dead_bukan_pending(self) -> None:
        # Kalau job seperti ini dikembalikan ke `pending`, ia jadi baris yang tidak
        # akan pernah layak diklaim dan run tidak pernah bisa dinyatakan selesai.
        self.seed("REC-001")
        self.burn("REC-001", MAX_ATTEMPTS - 1)
        late = NOW + MAX_ATTEMPTS * (BACKOFF_CAP_SECONDS + 60.0)
        store.claim_one(self.conn, "w-mati", now=late)
        self.assertEqual(self.job_row("REC-001")["attempts"], MAX_ATTEMPTS)
        recovered = store.recover_stuck(self.conn, lease_timeout=60.0, now=late + 120.0)
        self.assertEqual(recovered, {"pending": 0, "dead": 1})
        row = self.job_row("REC-001")
        self.assertEqual(row["status"], "dead")
        self.assertIn("habis", row["last_error"])

    def test_sapuan_pada_antrean_tanpa_job_nyangkut_tidak_menyentuh_apa_pun(self) -> None:
        self.seed("REC-001")
        store.claim_one(self.conn, "w-1", now=NOW)
        before = dict(self.job_row("REC-001"))
        self.assertEqual(
            store.recover_stuck(self.conn, lease_timeout=120.0, now=NOW + 10.0),
            {"pending": 0, "dead": 0},
        )
        self.assertEqual(dict(self.job_row("REC-001")), before)

    def test_worker_mati_lalu_job_dipulihkan_dan_berhasil_tanpa_duplikat(self) -> None:
        # Inti A10: satu job menempuh claimed -> (worker mati) -> pending -> ok.
        self.seed("REC-001")
        store.claim_one(self.conn, "w-mati", now=NOW)
        store.recover_stuck(self.conn, lease_timeout=60.0, now=NOW + 120.0)
        resumed = store.claim_one(self.conn, "w-hidup", now=NOW + 200.0)
        assert resumed is not None
        self.assertEqual(resumed.attempts, 2)
        store.mark_ok(
            self.conn, "REC-001", "SL-a6d5ec39",
            worker_id="w-hidup", started_at=NOW + 200.0, now=NOW + 201.0,
        )
        row = self.job_row("REC-001")
        self.assertEqual((row["status"], row["confirmation"]), ("ok", "SL-a6d5ec39"))
        duplicates = self.conn.execute(
            "SELECT COUNT(*) - COUNT(DISTINCT external_ref) FROM jobs"
        ).fetchone()[0]
        self.assertEqual(duplicates, 0)
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'ok' GROUP BY confirmation"
            ).fetchone()[0],
            1,
        )

    def test_pemilik_lama_ditolak_menulis_setelah_lease_pindah(self) -> None:
        # Worker yang cuma tergantung (bukan mati) bisa bangun setelah lease-nya
        # direbut. Ia tidak boleh menimpa hasil pemilik baru.
        self.seed("REC-001")
        store.claim_one(self.conn, "w-lama", now=NOW)
        store.recover_stuck(self.conn, lease_timeout=60.0, now=NOW + 120.0)
        store.claim_one(self.conn, "w-baru", now=NOW + 200.0)
        with self.assertRaisesRegex(store.StoreError, "dipegang 'w-baru'"):
            store.mark_ok(
                self.conn, "REC-001", "SL-a6d5ec39",
                worker_id="w-lama", started_at=NOW, now=NOW + 210.0,
            )


class TestJadwalSapuanLease(ResilienceTestCase):
    """R2: sapuan lease harus jatuh tempo karena waktu, bukan karena antrean kosong.

    Sebelum perbaikan, `store.recover_stuck` hanya dipanggil di cabang `job is None`
    putaran worker. Selama masih ada job layak klaim, cabang itu tidak pernah
    tersentuh, jadi job yatim menganggur sampai antrean habis — di run penuh P11
    terukur 27 menit, bukan setengah lease seperti bunyi D8.
    """

    def orphan(self, ref: str) -> None:
        """Tinggalkan satu job di `claimed` dengan lease yang sudah lewat jauh.

        Dipanggil dari dalam putaran, bukan di `setUp`: yatim yang sudah ada sebelum
        worker mulai ditolong sapuan startup, jadi ia tidak menguji apa pun tentang
        jadwal sapuan di dalam putaran. Yang diuji di sini adalah worker lain yang mati
        SETELAH run berjalan, selagi antrean masih penuh.
        """
        self.seed(ref)
        dead_since = time.time() - 10_000.0
        self.conn.execute(
            "UPDATE jobs SET status = 'claimed', worker_id = 'w-mati', attempts = 1,"
            " claimed_at = ?, updated_at = ? WHERE external_ref = ?",
            (dead_since, dead_since, ref),
        )

    def test_yatim_disapu_walau_antrean_tidak_pernah_kosong(self) -> None:
        self.seed(*(f"REC-{index:03d}" for index in range(20)))
        submitted: list[str] = []

        def submit(payload: dict[str, str]) -> worker.SubmitResult:
            if not submitted:  # worker tetangga mati tepat setelah job pertama
                self.orphan("REC-YATIM")
            submitted.append(payload["external_ref"])
            return _always_ok(payload)

        tally = worker._drain_queue(
            self.conn,
            submit,
            worker_id="w-hidup",
            max_jobs=10,  # antrean 20 job: `claim_one` tidak pernah mengembalikan None
            lease_timeout=60.0,
            monotonic=_FakeClock(step=5.0),  # setengah lease lewat di putaran ke-6
            sleep=_no_sleep,
        )

        self.assertEqual(tally["ok"], 10)
        # Antrean memang tidak pernah kosong selama putaran: 21 job, 10 diproses.
        self.assertGreater(store.counts(self.conn)["pending"], 0)
        row = self.job_row("REC-YATIM")
        self.assertNotEqual(row["status"], "claimed")
        self.assertNotEqual(row["worker_id"], "w-mati")
        # Baris audit sapuan adalah bukti permanennya: status job bisa maju lagi
        # setelah pulih, `attempts` tidak.
        sweeps = [
            attempt
            for attempt in self.attempt_rows("REC-YATIM")
            if attempt["outcome"] == "timeout" and "lease" in (attempt["error"] or "")
        ]
        self.assertEqual(len(sweeps), 1)

    def test_sapuan_tidak_dipanggil_sebelum_setengah_lease(self) -> None:
        # Pagar arah sebaliknya: sapuan yang terlalu rajin merebut job yang masih
        # dikerjakan worker hidup (D8), jadi jadwalnya tidak boleh tiap putaran.
        self.orphan("REC-YATIM")
        self.seed(*(f"REC-{index:03d}" for index in range(5)))
        calls: list[float] = []
        real_recover = store.recover_stuck

        def counted(conn, **kwargs):
            calls.append(0.0)
            return real_recover(conn, **kwargs)

        store.recover_stuck = counted
        self.addCleanup(setattr, store, "recover_stuck", real_recover)
        try:
            worker._drain_queue(
                self.conn,
                _always_ok,
                worker_id="w-hidup",
                max_jobs=3,
                lease_timeout=600.0,  # setengah lease = 300 dtk, jam palsu tak sampai
                monotonic=_FakeClock(step=5.0),
                sleep=_no_sleep,
            )
        finally:
            store.recover_stuck = real_recover
        # Hanya sapuan startup; tidak ada sapuan tambahan di dalam putaran.
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
