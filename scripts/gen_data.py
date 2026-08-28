"""Generate deterministic synthetic input data without retaining rows in memory."""

import argparse
import csv
import os
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

from faker import Faker
from openpyxl import Workbook

FIELDS = ("external_ref", "full_name", "email", "policy_no", "amount", "notes")
DEFAULT_DUPLICATES = 50


def validate_counts(rows: int, duplicates: int) -> None:
    if rows < 1:
        raise ValueError("rows harus lebih besar dari 0")
    if duplicates < 0 or duplicates >= rows:
        raise ValueError("duplicates harus di antara 0 dan rows - 1")


def iter_records(rows: int, seed: int, duplicates: int) -> Iterator[tuple[object, ...]]:
    """Yield valid synthetic rows; the final rows repeat the first natural keys."""
    validate_counts(rows, duplicates)
    fake = Faker("id_ID")
    fake.seed_instance(seed)
    unique_rows = rows - duplicates

    for index in range(1, rows + 1):
        ref_index = index if index <= unique_rows else index - unique_rows
        yield (
            f"REC-{ref_index:06d}",
            fake.name()[:120],
            fake.ascii_free_email(),
            f"POL-{index:08d}",
            Decimal(fake.random_int(min=100, max=100_000_000)) / 100,
            fake.sentence(nb_words=10)[:500],
        )


def generate_dataset(rows: int, seed: int, out: Path, duplicates: int = DEFAULT_DUPLICATES) -> None:
    """Write matching CSV and write-only XLSX datasets using one streaming pass."""
    validate_counts(rows, duplicates)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "records.csv"
    xlsx_path = out / "records.xlsx"
    csv_tmp = out / ".records.csv.tmp"
    xlsx_tmp = out / ".records.xlsx.tmp"
    existing = [path for path in (csv_path, xlsx_path) if path.exists()]
    if existing:
        raise FileExistsError(f"output sudah ada; data mentah tidak ditimpa: {existing[0]}")

    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet("records")
    worksheet.append(FIELDS)

    try:
        with csv_tmp.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(FIELDS)
            for record in iter_records(rows, seed, duplicates):
                writer.writerow(record)
                worksheet.append(record)
        workbook.save(xlsx_tmp)
        os.replace(csv_tmp, csv_path)
        os.replace(xlsx_tmp, xlsx_path)
    finally:
        csv_tmp.unlink(missing_ok=True)
        xlsx_tmp.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/input"))
    parser.add_argument("--duplicates", type=int, default=DEFAULT_DUPLICATES)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_dataset(args.rows, args.seed, args.out, args.duplicates)
    print(
        f"generated={args.rows} duplicates={args.duplicates} seed={args.seed} "
        f"out={args.out}"
    )


if __name__ == "__main__":
    main()
