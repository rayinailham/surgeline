#!/usr/bin/env python3
"""Pemindai rahasia & artefak runtime sebelum commit (P14, gerbang D13 / A12).

Dua tingkat, dua-duanya dicetak:

* **KEBOCORAN** (exit 1) — hal yang tidak boleh ada di repo sama sekali:
  kredensial/kunci/token, artefak runtime ter-track (`.env`, `data/`, `reports/`,
  `auth/`, `*.db`, `*.sqlite*`), entri `.gitignore` yang hilang, dan jalur absolut
  mesin pribadi di berkas yang dibaca klien (README, laporan, `assets/`).
* **CATATAN** (exit 0) — jalur mesin di dokumen kerja internal (`AGENTS.md`,
  `KICKSTART.md`, `phases/`, `env-check.md`, `docs/TOOLS.md`, `docs/TARGET.md`).
  Sengaja dibiarkan: itu memang catatan lingkungan. Dicetak supaya keputusan
  membuka repo (D16) diambil sadar, bukan karena kelupaan.

Pakai: `python scripts/secret_audit.py` atau `make audit`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Artefak runtime yang tidak boleh ter-track (AGENTS §4).
FORBIDDEN_TRACKED = (
    re.compile(r"(^|/)\.env(\.local)?$"),  # `.env.example` sengaja boleh
    re.compile(r"^data/"),
    re.compile(r"^reports/"),
    re.compile(r"(^|/)auth/"),
    re.compile(r"\.(db|sqlite)(-wal|-shm)?$"),
    re.compile(r"\.db-(wal|shm)$"),
)
# Perkecualian: contoh laporan tersanitasi memang sengaja masuk repo (P13).
TRACKED_ALLOW = (re.compile(r"^assets/sample_"),)

REQUIRED_GITIGNORE = (
    "data/",
    "reports/",
    "auth/",
    "*.db",
    "*.sqlite",
    ".env",
    ".venv/",
)

# Pola kredensial. Sengaja sempit supaya tidak berisik.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("kunci privat", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("token GitHub", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}")),
    ("token GitHub (pat)", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("kunci OpenAI/Anthropic", re.compile(r"\b(sk-[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9-]{20,})")),
    ("kunci akses AWS", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("token Slack", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
    ("token AWS/Google (generik)", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    (
        "kata sandi hardcoded",
        re.compile(
            r"(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*"
            r"['\"][^'\"\s${}<>]{8,}['\"]"
        ),
    ),
)

HOME_PATH = re.compile(r"/home/[A-Za-z0-9._-]+/")

# Dokumen kerja internal: jalur mesin di sini adalah catatan, bukan kebocoran.
INTERNAL_DOCS = {
    "AGENTS.md",
    "KICKSTART.md",
    "STATE.md",
    "PLAN.md",
    "env-check.md",
    "docs/TOOLS.md",
    "docs/TARGET.md",
    "scripts/secret_audit.py",
}
INTERNAL_PREFIXES = ("phases/",)

BINARY_SUFFIXES = {".xlsx", ".png", ".jpg", ".jpeg", ".mp4", ".pdf", ".ico", ".woff2"}


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str
    detail: str

    def line(self) -> str:
        return f"  [{self.kind}] {self.path}: {self.detail}"


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        capture_output=True, text=True, check=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def dirty_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "status", "--short"],
        capture_output=True, text=True, check=True,
    )
    paths = []
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        paths.append(line[3:].split(" -> ")[-1].strip().strip('"'))
    return paths


def _is_internal(path: str) -> bool:
    return path in INTERNAL_DOCS or path.startswith(INTERNAL_PREFIXES)


def check_tracked_artifacts(paths: list[str]) -> list[Finding]:
    findings = []
    for path in paths:
        if any(allow.search(path) for allow in TRACKED_ALLOW):
            continue
        for pattern in FORBIDDEN_TRACKED:
            if pattern.search(path):
                findings.append(
                    Finding("artefak", path, f"artefak runtime ter-track ({pattern.pattern})")
                )
                break
    return findings


def check_gitignore(root: Path) -> list[Finding]:
    path = root / ".gitignore"
    if not path.is_file():
        return [Finding("gitignore", ".gitignore", "berkas .gitignore tidak ada")]
    entries = {
        line.strip() for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    return [
        Finding("gitignore", ".gitignore", f"entri wajib hilang: {needed}")
        for needed in REQUIRED_GITIGNORE
        if needed not in entries
    ]


def scan_contents(root: Path, paths: list[str]) -> tuple[list[Finding], list[Finding]]:
    """Kembalikan (kebocoran, catatan)."""
    leaks: list[Finding] = []
    notes: list[Finding] = []
    for path in paths:
        file = root / path
        if not file.is_file() or file.suffix.lower() in BINARY_SUFFIXES:
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    leaks.append(Finding("rahasia", f"{path}:{number}", label))
            match = HOME_PATH.search(line)
            if match:
                where = Finding("jalur", f"{path}:{number}", f"jalur mesin {match.group(0)}…")
                (notes if _is_internal(path) else leaks).append(where)
    return leaks, notes


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, str]] = set()
    unique = []
    for finding in findings:
        key = (finding.kind, finding.path, finding.detail)
        if key not in seen:
            seen.add(key)
            unique.append(finding)
    return unique


def audit(root: Path) -> tuple[list[Finding], list[Finding]]:
    paths = tracked_files(root)
    leaks = check_tracked_artifacts(paths)
    leaks += check_tracked_artifacts(dirty_files(root))
    leaks += check_gitignore(root)
    content_leaks, notes = scan_contents(root, paths)
    return _dedupe(leaks + content_leaks), _dedupe(notes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)

    leaks, notes = audit(args.root)
    files = len(tracked_files(args.root))

    if notes:
        print(f"CATATAN ({len(notes)}) — jalur mesin di dokumen kerja internal, disengaja:")
        for finding in notes:
            print(finding.line())

    if leaks:
        print(f"\nKEBOCORAN ({len(leaks)}) — harus nol sebelum commit:")
        for finding in leaks:
            print(finding.line())
        return 1

    print(f"\naudit: {files} berkas ter-track dipindai, 0 kebocoran.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
