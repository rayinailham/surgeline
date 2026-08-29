"""Ukur throughput nyata satu run dan bandingkan beberapa N worker (P12, A7).

Read-only terhadap antrean (`mode=ro`, sama seperti `scripts/run_summary.py` dan
`src/dashboard.py`): modul ini tidak pernah menulis ke `queue.db`.

Angka yang dipakai:

- **Jendela** = `MIN(attempts.started_at)` .. `MAX(COALESCE(attempts.ended_at, started_at))`.
  Wall-clock nyata, termasuk waktu tunggu backoff (D7) dan jeda saat worker dibunuh —
  bukan penjumlahan waktu sibuk. Angka yang dijual ke klien harus angka jam dinding.
- **Throughput** = record `ok` per jendela. Job `failed`/`dead` tetap dihitung di
  `terminal_per_hour` supaya laju "antrean habis" juga terlihat, tapi janji ke klien
  memakai `ok` — hanya submission bernomor konfirmasi (D6) yang berarti.

Titik jenuh dicari dari kenaikan throughput antar N yang **diukur**, bukan diekstrapolasi
linear (jebakan yang dicatat `phases/phase-12-throughput.md`).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

SECONDS_PER_HOUR = 3600.0
SECONDS_PER_DAY = 86_400.0
#: Kenaikan throughput di bawah ambang ini dianggap "tidak lagi berarti" -> jenuh.
DEFAULT_SATURATION_GAIN = 0.10
#: Skala yang dijanjikan klien job 18; tidak pernah benar-benar dijalankan (D15).
DEFAULT_EXTRAPOLATION_RECORDS = 6_000_000


@dataclass(frozen=True)
class RunThroughput:
    """Laju satu run, seluruhnya dari `queue.db` run itu."""

    run_id: str
    workers: int
    jobs_total: int
    ok: int
    terminal: int
    attempts: int
    window_seconds: float
    ok_per_second: float
    ok_per_hour: float
    terminal_per_hour: float
    attempts_per_ok: float


@dataclass(frozen=True)
class ScalingRow:
    """Satu baris tabel skala: N worker vs laju, relatif terhadap N terkecil."""

    workers: int
    run_id: str
    ok: int
    window_seconds: float
    ok_per_hour: float
    speedup: float
    efficiency: float
    gain_over_previous: float | None


def connect_ro(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def _db_path(run_id: str) -> Path:
    return Path("data") / run_id / "queue.db"


def _workers_from_run_json(run_id: str) -> int | None:
    path = Path("data") / run_id / "run.json"
    if not path.exists():
        return None
    workers = json.loads(path.read_text(encoding="utf-8")).get("workers")
    return int(workers) if isinstance(workers, int) else None


def measure(run_id: str, *, workers: int | None = None, db: Path | None = None) -> RunThroughput:
    """Baca satu antrean dan hitung lajunya. Tidak menebak apa pun yang tidak ada di DB."""
    path = db or _db_path(run_id)
    if not path.exists():
        raise SystemExit(f"antrean tidak ada: {path}")
    if workers is None:
        workers = _workers_from_run_json(run_id) or 1

    conn = connect_ro(path)
    try:
        first, last = conn.execute(
            "SELECT MIN(started_at), MAX(COALESCE(ended_at, started_at)) FROM attempts"
        ).fetchone()
        status = dict(conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status"))
        jobs_total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        attempts = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    finally:
        conn.close()

    if first is None or last is None:
        raise SystemExit(f"run {run_id} belum punya satu pun percobaan")

    window = float(last) - float(first)
    ok = status.get("ok", 0)
    terminal = ok + status.get("failed", 0) + status.get("dead", 0)
    per_second = ok / window if window > 0 else 0.0
    return RunThroughput(
        run_id=run_id,
        workers=workers,
        jobs_total=jobs_total,
        ok=ok,
        terminal=terminal,
        attempts=attempts,
        window_seconds=round(window, 3),
        ok_per_second=round(per_second, 3),
        ok_per_hour=round(per_second * SECONDS_PER_HOUR, 1),
        terminal_per_hour=round(
            (terminal / window * SECONDS_PER_HOUR) if window > 0 else 0.0, 1
        ),
        attempts_per_ok=round(attempts / ok, 3) if ok else 0.0,
    )


def scaling_table(runs: list[RunThroughput]) -> list[ScalingRow]:
    """Urutkan hasil per N worker dan hitung speedup, efisiensi, dan kenaikan antar-N.

    `speedup` selalu relatif terhadap N terkecil yang **diukur** (biasanya 1), sehingga
    efisiensi = speedup / (N / N_terkecil) bisa dibaca sebagai "berapa persen dari
    penskalaan ideal yang benar-benar didapat".
    """
    if not runs:
        return []
    ordered = sorted(runs, key=lambda run: run.workers)
    baseline = ordered[0]
    rows: list[ScalingRow] = []
    for index, run in enumerate(ordered):
        previous = ordered[index - 1] if index else None
        speedup = run.ok_per_hour / baseline.ok_per_hour if baseline.ok_per_hour else 0.0
        ideal = run.workers / baseline.workers if baseline.workers else 0.0
        gain = None
        if previous is not None and previous.ok_per_hour:
            gain = run.ok_per_hour / previous.ok_per_hour - 1.0
        rows.append(
            ScalingRow(
                workers=run.workers,
                run_id=run.run_id,
                ok=run.ok,
                window_seconds=run.window_seconds,
                ok_per_hour=run.ok_per_hour,
                speedup=round(speedup, 3),
                efficiency=round(speedup / ideal, 3) if ideal else 0.0,
                gain_over_previous=round(gain, 4) if gain is not None else None,
            )
        )
    return rows


def saturation_workers(
    rows: list[ScalingRow], *, min_gain: float = DEFAULT_SATURATION_GAIN
) -> tuple[int | None, bool]:
    """Kembalikan `(N_jenuh, terbukti)`.

    `N_jenuh` = N terkecil yang setelahnya menambah worker menaikkan throughput
    **kurang dari** `min_gain`. `terbukti=False` berarti seluruh rentang yang diukur
    masih naik berarti — jenuhnya di luar rentang, dan itu harus ditulis apa adanya,
    bukan ditebak.
    """
    if len(rows) < 2:
        return (None, False)
    for index in range(1, len(rows)):
        gain = rows[index].gain_over_previous
        if gain is not None and gain < min_gain:
            return (rows[index - 1].workers, True)
    return (rows[-1].workers, False)


def extrapolate(records: int, ok_per_hour: float) -> tuple[float, float]:
    """(jam, hari) untuk `records` record pada laju terukur. Linear, sengaja telanjang."""
    if ok_per_hour <= 0:
        raise ValueError("ok_per_hour harus > 0")
    hours = records / ok_per_hour
    return (round(hours, 2), round(hours * SECONDS_PER_HOUR / SECONDS_PER_DAY, 2))


def _format_run(run: RunThroughput) -> str:
    return (
        f"run={run.run_id} workers={run.workers} ok={run.ok}/{run.jobs_total} "
        f"window={run.window_seconds:.1f}s ok/s={run.ok_per_second:.2f} "
        f"ok/jam={run.ok_per_hour:,.0f} terminal/jam={run.terminal_per_hour:,.0f} "
        f"attempts/ok={run.attempts_per_ok:.3f}"
    )


def _format_scaling(rows: list[ScalingRow]) -> str:
    lines = [
        "| N worker | run | ok | jendela (dtk) | record/jam | speedup | efisiensi | naik vs N sebelumnya |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        gain = "—" if row.gain_over_previous is None else f"{row.gain_over_previous * 100:+.1f}%"
        lines.append(
            f"| {row.workers} | `{row.run_id}` | {row.ok} | {row.window_seconds:.1f} | "
            f"{row.ok_per_hour:,.0f} | {row.speedup:.2f}× | {row.efficiency * 100:.0f}% | {gain} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", help="run_id tunggal di data/<run_id>/queue.db")
    parser.add_argument("--workers", type=int, help="N worker run itu (default: dari run.json)")
    parser.add_argument(
        "--scale",
        type=Path,
        help="manifest JSON [{run_id, workers}, ...] untuk tabel skala N worker",
    )
    parser.add_argument(
        "--extrapolate",
        type=int,
        default=DEFAULT_EXTRAPOLATION_RECORDS,
        help="jumlah record yang diekstrapolasi dari laju terbaik",
    )
    parser.add_argument("--json", action="store_true", help="keluarkan JSON, bukan teks")
    args = parser.parse_args(argv)

    if not args.run and not args.scale:
        parser.error("butuh --run atau --scale")

    payload: dict[str, object] = {}

    if args.run:
        single = measure(args.run, workers=args.workers)
        payload["run"] = asdict(single)
        if not args.json:
            print(_format_run(single))

    if args.scale:
        manifest = json.loads(args.scale.read_text(encoding="utf-8"))
        runs = [
            measure(entry["run_id"], workers=int(entry["workers"])) for entry in manifest
        ]
        rows = scaling_table(runs)
        best = max(rows, key=lambda row: row.ok_per_hour)
        jenuh, terbukti = saturation_workers(rows)
        hours, days = extrapolate(args.extrapolate, best.ok_per_hour)
        payload["scale"] = [asdict(row) for row in rows]
        payload["best"] = asdict(best)
        payload["saturation_workers"] = jenuh
        payload["saturation_proven"] = terbukti
        payload["extrapolation"] = {
            "records": args.extrapolate,
            "ok_per_hour": best.ok_per_hour,
            "hours": hours,
            "days": days,
        }
        if not args.json:
            print(_format_scaling(rows))
            catatan = "terbukti" if terbukti else "BELUM terbukti dalam rentang terukur"
            print(f"\ntitik jenuh: N={jenuh} ({catatan}, ambang {DEFAULT_SATURATION_GAIN:.0%})")
            print(
                f"terbaik: {best.ok_per_hour:,.0f} record/jam @ {best.workers} worker "
                f"-> {args.extrapolate:,} record ≈ {hours:,.1f} jam ≈ {days:,.1f} hari"
            )

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
