import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from src.load import LoadError, load_records
from src.schema import RECORD_FIELDS


def record(external_ref: str = "REC-001") -> dict[str, object]:
    return {
        "external_ref": external_ref,
        "full_name": "Budi Saputra",
        "email": "budi@example.org",
        "policy_no": "POL-0001",
        "amount": 125000.5,
        "notes": "Data sintetis.",
    }


class TestLoad(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "run" / "queue.db"

    def write_csv(self, rows: list[dict[str, object]]) -> Path:
        path = self.root / "records.csv"
        with path.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=RECORD_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def write_xlsx(self, rows: list[dict[str, object]]) -> Path:
        path = self.root / "records.xlsx"
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet()
        sheet.append(RECORD_FIELDS)
        for row in rows:
            sheet.append(tuple(row[field] for field in RECORD_FIELDS))
        workbook.save(path)
        return path

    def count(self) -> int:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        finally:
            conn.close()

    def test_load_file_kecil_semua_pending(self) -> None:
        stats = load_records(self.write_csv([record("REC-001"), record("REC-002")]), self.db)
        conn = sqlite3.connect(self.db)
        try:
            pending = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='pending'").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual((stats.read, stats.inserted), (2, 2))
        self.assertEqual(pending, 2)

    def test_duplikat_external_ref_ditolak_database(self) -> None:
        stats = load_records(self.write_xlsx([record(), record()]), self.db, batch_size=1)
        self.assertEqual((stats.read, stats.inserted, stats.duplicates), (2, 1, 1))
        self.assertEqual(self.count(), 1)

    def test_load_ulang_idempoten(self) -> None:
        source = self.write_csv([record("REC-001"), record("REC-002")])
        first = load_records(source, self.db)
        second = load_records(source, self.db)
        self.assertEqual((first.inserted, second.inserted, second.duplicates), (2, 0, 2))
        self.assertEqual(self.count(), 2)

    def test_payload_json_bisa_dibaca_balik(self) -> None:
        expected = record()
        load_records(self.write_xlsx([expected]), self.db)
        conn = sqlite3.connect(self.db)
        try:
            payload = json.loads(conn.execute("SELECT payload FROM jobs").fetchone()[0])
        finally:
            conn.close()
        self.assertEqual(payload, expected)

    def test_record_invalid_ditolak_sebelum_insert(self) -> None:
        invalid = record()
        invalid["amount"] = -1
        with self.assertRaisesRegex(LoadError, "baris 2: amount harus angka > 0"):
            load_records(self.write_csv([invalid]), self.db)
        self.assertEqual(self.count(), 0)

    def test_header_salah_ditolak(self) -> None:
        source = self.root / "records.csv"
        source.write_text("external_ref,full_name\nREC-1,Budi\n", encoding="utf-8")
        with self.assertRaisesRegex(LoadError, "header harus"):
            load_records(source, self.db)


if __name__ == "__main__":
    unittest.main()
