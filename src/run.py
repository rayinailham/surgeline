"""Jalankan beberapa worker Playwright paralel di atas satu antrean SQLite WAL."""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _run_worker(args: list[str]) -> int:
    return subprocess.run(args, check=False).returncode


def _attempt_count(run: str) -> int:
    with sqlite3.connect(Path("data") / run / "queue.db") as conn:
        return conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]


def run_workers(
    *,
    run: str,
    workers: int,
    limit: int,
    base_url: str,
    timeout_ms: int,
) -> tuple[float, list[int], int]:
    """Spawn N proses worker; `limit` dibagi agar total percobaan tidak melewatinya."""
    if workers < 1:
        raise ValueError("workers harus >= 1")
    if limit < 0:
        raise ValueError("limit harus >= 0")
    if limit and limit < workers:
        raise ValueError("limit harus 0 atau >= workers")

    quotas = [0] * workers
    if limit:
        each, extra = divmod(limit, workers)
        quotas = [each + (index < extra) for index in range(workers)]

    commands = []
    for index, quota in enumerate(quotas, start=1):
        command = [
            sys.executable,
            "-m",
            "src.worker",
            "--run",
            run,
            "--worker-id",
            f"w-{index}",
            "--base-url",
            base_url,
            "--timeout-ms",
            str(timeout_ms),
        ]
        if limit:
            command.extend(("--max-jobs", str(quota)))
        commands.append(command)

    attempts_before = _attempt_count(run)
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return_codes = list(executor.map(_run_worker, commands))
    return time.monotonic() - started, return_codes, _attempt_count(run) - attempts_before


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="run_id di data/<run_id>/queue.db")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="batas total job (0 = sampai habis)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8110")
    parser.add_argument("--timeout-ms", type=int, default=5_000)
    args = parser.parse_args()

    try:
        elapsed, return_codes, processed = run_workers(
            run=args.run,
            workers=args.workers,
            limit=args.limit,
            base_url=args.base_url,
            timeout_ms=args.timeout_ms,
        )
    except ValueError as error:
        parser.error(str(error))

    rate = processed / elapsed
    print(
        f"workers={args.workers} processed={processed} elapsed={elapsed:.3f}s "
        f"throughput={rate:.2f} job/s return_codes={return_codes}"
    )
    return 0 if all(code == 0 for code in return_codes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
