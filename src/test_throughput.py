"""Throughput P12: jendela laju, titik jenuh, dan ekstrapolasi. Tanpa browser, tanpa target.

Angka yang dijual ke klien lahir dari fungsi-fungsi ini, jadi yang diuji bukan "tidak
error" melainkan aritmetikanya: jendela wall-clock, kenaikan antar-N, dan kapan modul
BOLEH mengaku menemukan titik jenuh.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src import throughput
from src.schema import init_db

NOW = 1_000_000.0


def _row(workers: int, ok_per_hour: float, run_id: str = "r") -> throughput.RunThroughput:
    return throughput.RunThroughput(
        run_id=f"{run_id}-n{workers}",
        workers=workers,
        jobs_total=100,
        ok=100,
        terminal=100,
        attempts=100,
        window_seconds=3600.0,
        ok_per_second=ok_per_hour / 3600.0,
        ok_per_hour=ok_per_hour,
        terminal_per_hour=ok_per_hour,
        attempts_per_ok=1.0,
    )


class MeasureTestCase(unittest.TestCase):
    """`measure` hanya boleh melaporkan apa yang ada di `queue.db`."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / "queue.db"
        self.conn = init_db(self.db)
        self.addCleanup(self.conn.close)

    def seed_job(self, ref: str, status: str) -> None:
        self.conn.execute(
            "INSERT INTO jobs (external_ref, payload, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (ref, json.dumps({"external_ref": ref}), status, NOW, NOW),
        )

    def seed_attempt(self, ref: str, started: float, ended: float | None, outcome: str) -> None:
        self.conn.execute(
            "INSERT INTO attempts (external_ref, worker_id, started_at, ended_at, outcome)"
            " VALUES (?, ?, ?, ?, ?)",
            (ref, "w-1", started, ended, outcome),
        )

    def test_jendela_dari_percobaan_pertama_sampai_terakhir(self) -> None:
        """Jendela = wall-clock percobaan, termasuk jeda backoff, bukan waktu sibuk."""
        for index in range(2):
            self.seed_job(f"REC-{index}", "ok")
        # Dua percobaan berdurasi 1 dtk masing-masing, tapi terpisah jeda 3598 dtk.
        self.seed_attempt("REC-0", NOW, NOW + 1.0, "ok")
        self.seed_attempt("REC-1", NOW + 3599.0, NOW + 3600.0, "ok")
        self.conn.commit()

        result = throughput.measure("uji", workers=1, db=self.db)

        self.assertEqual(result.window_seconds, 3600.0)
        self.assertEqual(result.ok, 2)
        self.assertEqual(result.ok_per_hour, 2.0)

    def test_hanya_ok_yang_dihitung_throughput(self) -> None:
        """`failed`/`dead` masuk `terminal_per_hour`, tapi tidak pernah dijual sbg sukses (D6)."""
        self.seed_job("REC-ok", "ok")
        self.seed_job("REC-failed", "failed")
        self.seed_job("REC-dead", "dead")
        self.seed_attempt("REC-ok", NOW, NOW + 1.0, "ok")
        self.seed_attempt("REC-failed", NOW, NOW + 1800.0, "permanent")
        self.seed_attempt("REC-dead", NOW, NOW + 3600.0, "retryable")
        self.conn.commit()

        result = throughput.measure("uji", workers=2, db=self.db)

        self.assertEqual(result.ok, 1)
        self.assertEqual(result.terminal, 3)
        self.assertEqual(result.ok_per_hour, 1.0)
        self.assertEqual(result.terminal_per_hour, 3.0)
        self.assertEqual(result.attempts_per_ok, 3.0)

    def test_percobaan_tanpa_ended_at_tetap_masuk_jendela(self) -> None:
        """Worker yang mati di tengah (P9) meninggalkan `ended_at` NULL; jendela tidak boleh None."""
        self.seed_job("REC-0", "ok")
        self.seed_attempt("REC-0", NOW, None, "ok")
        self.seed_attempt("REC-0", NOW + 10.0, None, "ok")
        self.conn.commit()

        result = throughput.measure("uji", workers=1, db=self.db)

        self.assertEqual(result.window_seconds, 10.0)

    def test_antrean_tanpa_percobaan_ditolak(self) -> None:
        self.seed_job("REC-0", "pending")
        self.conn.commit()

        with self.assertRaises(SystemExit):
            throughput.measure("uji", workers=1, db=self.db)

    def test_measure_tidak_bisa_menulis_antrean(self) -> None:
        """Koneksi `mode=ro`: modul laporan tidak boleh menyentuh sumber kebenaran."""
        self.seed_job("REC-0", "ok")
        self.seed_attempt("REC-0", NOW, NOW + 1.0, "ok")
        self.conn.commit()

        readonly = throughput.connect_ro(self.db)
        self.addCleanup(readonly.close)
        with self.assertRaises(sqlite3.OperationalError):
            readonly.execute("DELETE FROM jobs")


class ScalingTestCase(unittest.TestCase):
    def test_speedup_dan_efisiensi_relatif_ke_n_terkecil(self) -> None:
        rows = throughput.scaling_table([_row(4, 30_000.0), _row(1, 10_000.0)])

        self.assertEqual([row.workers for row in rows], [1, 4])
        self.assertEqual(rows[1].speedup, 3.0)
        self.assertEqual(rows[1].efficiency, 0.75)
        self.assertIsNone(rows[0].gain_over_previous)
        self.assertEqual(rows[1].gain_over_previous, 2.0)

    def test_jenuh_terbukti_saat_kenaikan_jatuh_di_bawah_ambang(self) -> None:
        rows = throughput.scaling_table(
            [_row(1, 10_000.0), _row(2, 18_000.0), _row(4, 18_500.0)]
        )

        self.assertEqual(throughput.saturation_workers(rows), (2, True))

    def test_jenuh_belum_terbukti_kalau_masih_naik_berarti(self) -> None:
        """Jangan pernah mengaku menemukan titik jenuh yang tidak diukur (jebakan P12)."""
        rows = throughput.scaling_table([_row(1, 10_000.0), _row(2, 19_000.0)])

        self.assertEqual(throughput.saturation_workers(rows), (2, False))

    def test_satu_titik_bukan_bukti_jenuh(self) -> None:
        rows = throughput.scaling_table([_row(4, 60_000.0)])

        self.assertEqual(throughput.saturation_workers(rows), (None, False))

    def test_penurunan_throughput_dihitung_jenuh(self) -> None:
        rows = throughput.scaling_table(
            [_row(8, 80_000.0), _row(16, 76_000.0)]
        )

        self.assertEqual(rows[1].gain_over_previous, -0.05)
        self.assertEqual(throughput.saturation_workers(rows), (8, True))


class ExtrapolationTestCase(unittest.TestCase):
    def test_enam_juta_record_pada_laju_terukur(self) -> None:
        self.assertEqual(throughput.extrapolate(6_000_000, 100_000.0), (60.0, 2.5))

    def test_laju_nol_ditolak(self) -> None:
        with self.assertRaises(ValueError):
            throughput.extrapolate(6_000_000, 0.0)


if __name__ == "__main__":
    unittest.main()
