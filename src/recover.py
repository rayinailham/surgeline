"""Sapuan lease berdiri sendiri: tarik job `claimed` yang ditinggal mati worker (D8).

Worker sudah menyapu sendiri saat start dan berkala (`src/worker.py`), tapi sapuan
terpisah tetap perlu: setelah seluruh run dimatikan paksa (P9) tidak ada satu pun
worker yang hidup untuk menyapu, dan bukti pemulihan harus bisa dijalankan sebagai
satu langkah yang terlihat, bukan efek samping di dalam loop worker.

    uv run --no-sync python -m src.recover --run <run_id> [--lease-timeout 120]
"""

from __future__ import annotations

import argparse
from pathlib import Path

if __package__:
    from . import store
    from .schema import LEASE_TIMEOUT_SECONDS, connect
else:  # dijalankan sebagai `python src/recover.py`
    import store
    from schema import LEASE_TIMEOUT_SECONDS, connect


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", help="run_id; antrean dibaca dari data/<run_id>/queue.db")
    parser.add_argument("--db", type=Path, help="path queue.db eksplisit (menang atas --run)")
    parser.add_argument(
        "--lease-timeout",
        type=float,
        default=LEASE_TIMEOUT_SECONDS,
        help="detik sebelum job `claimed` dianggap yatim (D8)",
    )
    args = parser.parse_args(argv)

    database = args.db if args.db is not None else Path("data") / (args.run or "") / "queue.db"
    if not args.db and not args.run:
        parser.error("butuh --run <run_id> atau --db <path>")
    if not database.is_file():
        parser.error(f"antrean tidak ditemukan: {database}")

    conn = connect(database)
    try:
        recovered = store.recover_stuck(conn, lease_timeout=args.lease_timeout)
        counts = store.counts(conn)
    finally:
        conn.close()

    print(
        f"lease={args.lease_timeout:.0f}s recovered_pending={recovered['pending']} "
        f"recovered_dead={recovered['dead']} "
        + " ".join(f"{status}={count}" for status, count in sorted(counts.items()))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
