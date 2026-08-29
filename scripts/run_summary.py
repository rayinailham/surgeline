#!/usr/bin/env python3
"""Ringkas satu run antrean jadi `data/<run_id>/run.json` (kontrak SCHEMA §2).

Dipakai P11 untuk menutup run penuh, dan P12/P13 untuk membaca angka yang sama
tanpa mengetik ulang query. Read-only terhadap antrean (`mode=ro`).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

TERMINAL = ("ok", "failed", "dead")


def connect_ro(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def summarize(run: str, *, workers: int, started_at: float | None) -> dict[str, object]:
    directory = Path("data") / run
    db = directory / "queue.db"
    if not db.exists():
        raise SystemExit(f"antrean tidak ada: {db}")

    conn = connect_ro(db)
    try:
        scalar = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        status = dict(conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status"))
        outcome = dict(conn.execute("SELECT outcome, COUNT(*) FROM attempts GROUP BY outcome"))
        finished_at = scalar("SELECT MAX(updated_at) FROM jobs")
        summary: dict[str, object] = {
            "run_id": run,
            "schema_version": int(
                scalar("SELECT value FROM meta WHERE key = 'schema_version'")
            ),
            "workers": workers,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": (
                round(finished_at - started_at, 3)
                if started_at is not None and finished_at is not None
                else None
            ),
            "jobs_total": scalar("SELECT COUNT(*) FROM jobs"),
            "status": status,
            "terminal": sum(status.get(name, 0) for name in TERMINAL),
            "non_terminal": status.get("pending", 0) + status.get("claimed", 0),
            "attempts_total": scalar("SELECT COUNT(*) FROM attempts"),
            "attempts_by_outcome": outcome,
            "duplicate_external_ref": scalar(
                "SELECT COUNT(*) - COUNT(DISTINCT external_ref) FROM jobs"
            ),
            "duplicate_confirmation": scalar(
                "SELECT COUNT(*) - COUNT(DISTINCT confirmation) FROM jobs WHERE status = 'ok'"
            ),
            "ok_without_confirmation": scalar(
                "SELECT COUNT(*) FROM jobs "
                "WHERE status = 'ok' AND (confirmation IS NULL OR confirmation = '')"
            ),
            "dead_without_last_error": scalar(
                "SELECT COUNT(*) FROM jobs WHERE status = 'dead' AND last_error IS NULL"
            ),
            "generated_at": time.time(),
        }
    finally:
        conn.close()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="run_id di data/<run_id>/queue.db")
    parser.add_argument("--workers", type=int, default=4, help="N worker yang dipakai run ini")
    parser.add_argument(
        "--started-at",
        type=float,
        default=None,
        help="epoch mulai run (default: baca data/<run_id>/start_epoch bila ada)",
    )
    args = parser.parse_args()

    started_at = args.started_at
    if started_at is None:
        marker = Path("data") / args.run / "start_epoch"
        if marker.exists():
            started_at = float(marker.read_text().strip())

    summary = summarize(args.run, workers=args.workers, started_at=started_at)
    destination = Path("data") / args.run / "run.json"
    destination.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"ditulis: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
