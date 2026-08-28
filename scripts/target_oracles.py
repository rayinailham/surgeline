#!/usr/bin/env python3
"""Oracle P2: buktikan chaos target 5%, tiga mode, dan reproducible."""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
from collections import Counter

import httpx

URL = "http://127.0.0.1:8110"
COUNT = 2_000
RATE = 0.05
SEED = "p2-oracle-2026"
DELAY_SECONDS = 0.2
MODES = ("server_error", "slow", "validation")


def expected_mode(external_ref: str) -> str | None:
    value = int.from_bytes(hashlib.sha256(f"{SEED}{external_ref}".encode()).digest(), "big")
    if value % 1_000_000 / 1_000_000 >= RATE:
        return None
    return MODES[value % 3]


def compose(*args: str, env: dict[str, str]) -> None:
    subprocess.run(["docker", "compose", *args], check=True, env=env)


def wait_until_healthy(client: httpx.Client) -> None:
    for _ in range(30):
        try:
            if client.get(f"{URL}/health").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("target oracle tidak healthy setelah 15 detik")


def submit(client: httpx.Client, external_ref: str) -> tuple[str, str | None, int, float]:
    started = time.monotonic()
    response = client.post(
        f"{URL}/submit",
        data={
            "external_ref": external_ref,
            "full_name": "Data Sintetis Oracle",
            "email": "oracle@example.test",
            "policy_no": "POL-ORACLE",
            "amount": "1000",
            "notes": "P2 target oracle",
        },
    )
    return (
        external_ref,
        response.headers.get("X-SurgeLine-Chaos"),
        response.status_code,
        time.monotonic() - started,
    )


def run_once(run_number: int, env: dict[str, str]) -> dict[str, str | None]:
    compose("down", env=env)
    compose("up", "-d", "--build", env=env)
    refs = [f"ORACLE-{index:06d}" for index in range(COUNT)]
    with httpx.Client(timeout=10.0) as client:
        wait_until_healthy(client)
        results = [submit(client, ref) for ref in refs]

    observed: dict[str, str | None] = {}
    status_by_mode = {None: 200, "server_error": 500, "slow": 200, "validation": 422}
    for external_ref, mode, status, elapsed in results:
        expected = expected_mode(external_ref)
        assert mode == expected, f"{external_ref}: mode {mode!r}, expected {expected!r}"
        assert status == status_by_mode[expected], (
            f"{external_ref}: HTTP {status}, expected {status_by_mode[expected]}"
        )
        if expected == "slow":
            assert elapsed >= DELAY_SECONDS * 0.8, (
                f"{external_ref}: mode slow hanya {elapsed:.3f} detik"
            )
        observed[external_ref] = mode

    counts = Counter(mode or "normal" for mode in observed.values())
    marked = COUNT - counts["normal"]
    print(
        f"run {run_number}: N={COUNT} marked={marked} rate={marked / COUNT:.2%} "
        f"server_error={counts['server_error']} slow={counts['slow']} "
        f"validation={counts['validation']} normal={counts['normal']}"
    )
    return observed


def main() -> None:
    env = os.environ | {
        "SURGELINE_CHAOS_RATE": str(RATE),
        "SURGELINE_CHAOS_SEED": SEED,
        "SURGELINE_CHAOS_DELAY_SECONDS": str(DELAY_SECONDS),
    }
    try:
        first = run_once(1, env)
        second = run_once(2, env)
        marked = {ref for ref, mode in first.items() if mode is not None}
        assert abs(len(marked) / COUNT - RATE) <= 0.015, "rate di luar toleransi 3.5%-6.5%"
        assert set(first.values()) >= {None, *MODES}, "tidak semua mode chaos muncul"
        assert first == second, "dua run dengan seed sama menghasilkan nasib berbeda"
        print(f"reproducible: {len(marked)} external_ref chaos identik; diff=0")
        print("target-oracles: PASS")
    finally:
        compose("down", env=env)


if __name__ == "__main__":
    main()
