"""Dashboard P10: angka wajib sama persis dengan DB, dan read-only.

Tanpa browser, tanpa uvicorn: `TestClient` memanggil app di proses ini, dan DB-nya
antrean sungguhan yang dibuat `init_db` di direktori sementara. Waktu disuntik lewat
`now=`/`window=` supaya jendela throughput tidak berkedip saat mesin sibuk.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from src import dashboard, store
from src.schema import JOB_STATUSES, connect, init_db

NOW = 1_000_000.0


class DashboardTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.data_dir = Path(self.directory.name) / "data"
        self.run = "p10-test"
        self.db = self.data_dir / self.run / "queue.db"
        self.conn = init_db(self.db)
        self.addCleanup(self.conn.close)

    # -- helper -----------------------------------------------------------

    def seed(self, status: str, count: int, *, start: int = 0) -> None:
        """Sisipkan job langsung di status tertentu (dashboard tidak peduli caranya)."""
        self.conn.executemany(
            "INSERT INTO jobs (external_ref, payload, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                (f"{status}-{index}", json.dumps({"external_ref": f"{status}-{index}"}),
                 status, NOW, NOW)
                for index in range(start, start + count)
            ),
        )

    def db_counts(self) -> dict[str, int]:
        """Angka pembanding: query mentah, bukan lewat kode dashboard (A6)."""
        counts = dict.fromkeys(sorted(JOB_STATUSES), 0)
        with closing(sqlite3.connect(self.db)) as raw:
            for status, number in raw.execute(
                "SELECT status, COUNT(*) FROM jobs GROUP BY status"
            ):
                counts[status] = number
        return counts

    def client(self, **kwargs) -> TestClient:
        app = dashboard.create_app(self.run, data_dir=self.data_dir, **kwargs)
        client = TestClient(app)
        self.addCleanup(client.close)
        return client

    # -- angka cocok DB ---------------------------------------------------

    def test_angka_api_sama_dengan_group_by_status(self) -> None:
        self.seed("pending", 7)
        self.seed("claimed", 3)
        self.seed("ok", 11)
        self.seed("failed", 2)
        self.seed("dead", 1)

        payload = self.client().get("/api/stats").json()

        expected = self.db_counts()
        for status, number in expected.items():
            self.assertEqual(payload[status], number, status)
        self.assertEqual(payload["total"], sum(expected.values()))
        self.assertEqual(payload["done"], expected["ok"] + expected["failed"] + expected["dead"])
        self.assertEqual(payload["remaining"], expected["pending"] + expected["claimed"])

    def test_angka_fragment_html_sama_dengan_db(self) -> None:
        """Yang dilihat mata di fragment HTMX, bukan hanya JSON, harus cocok DB."""
        self.seed("ok", 5)
        self.seed("pending", 4)

        body = self.client().get("/stats").text

        for status, label in dashboard.STATUS_LABELS:
            self.assertRegex(
                body,
                rf"{label} <code>{status}</code></td><td class=\"num\">{self.db_counts()[status]}</td>",
            )

    def test_semua_status_muncul_walau_nol(self) -> None:
        """Kartu tidak boleh hilang di tengah run; nol tetap ditampilkan sebagai 0."""
        payload = self.client().get("/api/stats").json()
        for status in sorted(JOB_STATUSES):
            self.assertEqual(payload[status], 0, status)
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["percent_done"], 0.0)

    def test_angka_ikut_berubah_saat_antrean_berubah(self) -> None:
        """Poll kedua membaca DB lagi, bukan potret yang di-cache saat startup."""
        client = self.client()
        self.seed("pending", 2)
        self.assertEqual(client.get("/api/stats").json()["pending"], 2)

        self.seed("pending", 3, start=2)
        self.assertEqual(client.get("/api/stats").json()["pending"], 5)

    # -- throughput -------------------------------------------------------

    def record_ok(self, ref: str, ended_at: float) -> None:
        self.conn.execute(
            "INSERT INTO jobs (external_ref, payload, status, created_at, updated_at)"
            " VALUES (?, ?, 'ok', ?, ?)",
            (ref, json.dumps({"external_ref": ref}), NOW, NOW),
        )
        store.record_attempt(
            self.conn, ref, worker_id="w-1", started_at=ended_at - 0.2,
            ended_at=ended_at, outcome="ok", confirmation=f"SL-{ref}",
        )

    def test_throughput_hanya_menghitung_sukses_di_jendela(self) -> None:
        for index in range(6):
            self.record_ok(f"baru-{index}", NOW - 10)
        for index in range(99):
            self.record_ok(f"lama-{index}", NOW - 600)  # di luar jendela 60 dtk

        rate = dashboard.throughput(self.conn, now=NOW, window=60.0)

        self.assertEqual(rate, 6.0)  # 6 sukses / 60 dtk -> 6,0 per menit

    def test_throughput_mengabaikan_percobaan_gagal(self) -> None:
        """Angka throughput adalah submission berhasil, bukan lalu lintas percobaan."""
        self.record_ok("sukses-1", NOW - 5)
        self.conn.execute(
            "INSERT INTO jobs (external_ref, payload, created_at, updated_at)"
            " VALUES ('gagal-1', '{}', ?, ?)", (NOW, NOW),
        )
        for outcome in ("retryable", "timeout", "permanent"):
            store.record_attempt(
                self.conn, "gagal-1", worker_id="w-1", started_at=NOW - 6,
                ended_at=NOW - 5, outcome=outcome, error="chaos",
            )

        self.assertEqual(dashboard.throughput(self.conn, now=NOW, window=60.0), 1.0)

    # -- read-only & ketahanan --------------------------------------------

    def test_koneksi_dashboard_menolak_menulis(self) -> None:
        """Worker sedang menulis di DB yang sama; dashboard tidak boleh bisa ikut."""
        conn = connect(self.db, read_only=True)
        self.addCleanup(conn.close)

        with self.assertRaises(sqlite3.OperationalError) as raised:
            conn.execute(
                "INSERT INTO jobs (external_ref, payload, created_at, updated_at)"
                " VALUES ('x', '{}', 0, 0)"
            )

        self.assertIn("readonly", str(raised.exception).lower())

    def test_koneksi_read_only_tetap_membaca_dan_tidak_mengubah_journal_mode(self) -> None:
        self.seed("ok", 3)
        conn = connect(self.db, read_only=True)
        self.addCleanup(conn.close)

        self.assertEqual(store.counts(conn)["ok"], 3)
        self.assertEqual(
            conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal"
        )

    def test_halaman_tetap_hidup_saat_antrean_hilang(self) -> None:
        """Run dibunuh / DB belum ada: halaman 200 + pesan, bukan 500 (DoD P10)."""
        client = dashboard.create_app("run-hantu", data_dir=self.data_dir)
        with TestClient(client) as probe:
            page = probe.get("/")
            fragment = probe.get("/stats")
            api = probe.get("/api/stats")

        self.assertEqual(page.status_code, 200)
        self.assertEqual(fragment.status_code, 200)
        self.assertIn("antrean belum ada", fragment.text)
        self.assertEqual(api.status_code, 503)
        self.assertIn("antrean belum ada", api.json()["error"])

    def test_membaca_antrean_yang_ditinggal_worker_mati(self) -> None:
        """`kill -9` meninggalkan job `claimed` + file WAL panas; dashboard tetap baca."""
        self.seed("claimed", 4)
        self.seed("ok", 6)
        self.conn.execute("UPDATE jobs SET worker_id = 'w-mati', claimed_at = ? "
                          "WHERE status = 'claimed'", (NOW,))
        # sengaja TIDAK di-checkpoint/close: meniru worker yang mati mendadak.

        payload = self.client().get("/api/stats").json()

        self.assertEqual(payload["claimed"], 4)
        self.assertEqual(payload["ok"], 6)

    # -- kontrak halaman ---------------------------------------------------

    def test_halaman_memuat_polling_htmx_dua_detik(self) -> None:
        body = self.client().get("/").text
        self.assertIn('hx-get="/stats"', body)
        self.assertIn('hx-trigger="every 2s"', body)
        self.assertIn('src="/static/htmx.min.js"', body)

    def test_htmx_dilayani_lokal_bukan_cdn(self) -> None:
        """Deliverable harus jalan tanpa internet di mesin klien (D2/D5)."""
        response = self.client().get("/static/htmx.min.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("htmx", response.text[:200])

    def test_default_host_localhost_dan_port_8120(self) -> None:
        """Tanpa auth (D11) -> tidak pernah 0.0.0.0; port dikunci D9."""
        self.assertEqual(dashboard.DEFAULT_HOST, "127.0.0.1")
        self.assertEqual(dashboard.DEFAULT_PORT, 8120)

    def test_run_dipilih_terbaru_saat_tidak_disebut(self) -> None:
        init_db(self.data_dir / "run-lama" / "queue.db").close()
        baru = self.data_dir / "run-baru" / "queue.db"
        init_db(baru).close()
        import os
        os.utime(baru, (NOW + 10, NOW + 10))
        os.utime(self.data_dir / "run-lama" / "queue.db", (NOW, NOW))
        os.utime(self.db, (NOW - 10, NOW - 10))

        self.assertEqual(dashboard.resolve_run(None, data_dir=self.data_dir), "run-baru")
        self.assertEqual(dashboard.resolve_run(self.run, data_dir=self.data_dir), self.run)

    def test_tanpa_antrean_sama_sekali_ditolak_dengan_pesan_jelas(self) -> None:
        kosong = Path(self.directory.name) / "kosong"
        with self.assertRaises(dashboard.DashboardError):
            dashboard.resolve_run(None, data_dir=kosong)


if __name__ == "__main__":
    unittest.main()
