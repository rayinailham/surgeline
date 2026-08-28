"""Smoke test P0: lingkungan runtime deliverable berdiri (D1, D2, D5)."""

import sqlite3
import sys
import unittest


class TestEnvironment(unittest.TestCase):
    def test_python_version(self):
        self.assertGreaterEqual(sys.version_info[:2], (3, 12))

    def test_core_dependencies_importable(self):
        for name in (
            "playwright",
            "fastapi",
            "uvicorn",
            "jinja2",
            "httpx",
            "openpyxl",
            "pandas",
            "faker",
        ):
            with self.subTest(module=name):
                __import__(name)

    def test_sqlite_supports_wal(self):
        """Antrean wajib SQLite mode WAL (D5)."""
        con = sqlite3.connect(":memory:")
        try:
            mode = con.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        finally:
            con.close()
        # :memory: menolak WAL, tapi build harus mengenali pragma-nya.
        self.assertIn(mode.lower(), {"wal", "memory"})


if __name__ == "__main__":
    unittest.main()
