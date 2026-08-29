#!/usr/bin/env python3
"""Ukur laju SurgeLine pada beberapa N worker di atas subset input yang sama (P12).

Adil = tiap N mendapat antrean baru dari **file input yang sama**, sehingga himpunan
`external_ref`-nya identik. Chaos target deterministik dari `sha256(seed + external_ref)`
(D3, `docs/CHAOS.md`) dan diputuskan **sebelum** penyimpanan idempoten, jadi tiap N
menghadapi himpunan kegagalan yang persis sama: beda angka = beda jumlah worker, bukan
beda nasib.

Satu run = satu direktori `data/<label>-n<N>/`; data mentah tidak pernah ditimpa (D5).
Hasilnya ditulis sebagai manifest untuk `src/throughput.py --scale`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def _run(command: list[str]) -> str:
    print(f"$ {' '.join(command)}", flush=True)
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    output = completed.stdout.strip()
    if output:
        print(output, flush=True)
    return output


def bench(
    *,
    label: str,
    workers: list[int],
    input_path: Path,
    base_url: str,
    timeout_ms: int,
) -> list[dict[str, object]]:
    manifest: list[dict[str, object]] = []
    for count in workers:
        run_id = f"{label}-n{count}"
        directory = Path("data") / run_id
        if directory.exists():
            raise SystemExit(f"{directory} sudah ada; pilih --label lain (data mentah D5)")
        _run(
            [sys.executable, "-m", "src.load", "--input", str(input_path), "--run", run_id]
        )
        started = time.time()
        _run(
            [
                sys.executable,
                "-m",
                "src.run",
                "--run",
                run_id,
                "--workers",
                str(count),
                "--base-url",
                base_url,
                "--timeout-ms",
                str(timeout_ms),
            ]
        )
        _run(
            [
                sys.executable,
                "scripts/run_summary.py",
                "--run",
                run_id,
                "--workers",
                str(count),
                "--started-at",
                str(started),
            ]
        )
        manifest.append({"run_id": run_id, "workers": count})
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="prefix run_id, mis. p12")
    parser.add_argument(
        "--workers", type=int, nargs="+", required=True, help="daftar N worker, mis. 1 2 4 8"
    )
    parser.add_argument("--input", type=Path, default=Path("data/p12/subset.csv"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8110")
    parser.add_argument("--timeout-ms", type=int, default=5_000)
    parser.add_argument(
        "--manifest", type=Path, default=None, help="default: data/<label>/scale.json"
    )
    args = parser.parse_args(argv)

    manifest_path = args.manifest or Path("data") / args.label / "scale.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = bench(
        label=args.label,
        workers=args.workers,
        input_path=args.input,
        base_url=args.base_url,
        timeout_ms=args.timeout_ms,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
