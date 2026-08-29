"""Regresi cold-start target (temuan audit P11): `_connect` harus aman dari race.

Beberapa thread yang menabrak container segar sama-sama memanggil `_connect`.
Sebelum perbaikan P14 tiap thread membuka koneksi sendiri lalu menjalankan
`PRAGMA journal_mode=WAL` bersamaan, dan yang kalah membalas HTTP 500 asli
(`database is locked`) — di luar chaos D3.
"""

from __future__ import annotations

import importlib
import sqlite3
import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import target.app as app


class ColdStartConnectTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._db_path = app.DB_PATH
        self._conn = app._conn
        app.DB_PATH = str(Path(self._tmp.name) / "state" / "target.db")
        app._conn = None

        def restore() -> None:
            if app._conn is not None:
                app._conn.close()
            app._conn = self._conn
            app.DB_PATH = self._db_path

        self.addCleanup(restore)

    def test_concurrent_connect_yields_one_connection_and_no_lock_error(self) -> None:
        threads_n = 16
        barrier = threading.Barrier(threads_n)
        conns: list[sqlite3.Connection] = []
        errors: list[BaseException] = []
        guard = threading.Lock()

        def worker() -> None:
            barrier.wait()
            try:
                conn = app._connect()
            except BaseException as exc:  # noqa: BLE001 - dicatat untuk assert
                with guard:
                    errors.append(exc)
                return
            with guard:
                conns.append(conn)

        threads = [threading.Thread(target=worker) for _ in range(threads_n)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [], f"cold-start masih melempar: {errors}")
        self.assertEqual(len(conns), threads_n)
        self.assertEqual(
            len({id(conn) for conn in conns}), 1, "harus satu koneksi proses-lebar"
        )

    def test_connect_sets_wal_and_busy_timeout(self) -> None:
        conn = app._connect()
        self.assertEqual(
            conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal"
        )
        self.assertGreaterEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], 15000)


if __name__ == "__main__":
    unittest.main()
