"""Pemindai rahasia P14 (A12) — dibuktikan menangkap, bukan sekadar lulus.

Tiap test membuat repo git sekali-pakai, menanam satu jenis kebocoran, lalu
memastikan audit menemukannya. Ada juga test repo bersih (0 temuan) dan test
bahwa repo SurgeLine sendiri lulus.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import secret_audit  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
CLEAN_GITIGNORE = "\n".join(secret_audit.REQUIRED_GITIGNORE) + "\n"
HOME_SAMPLE = "/" + "home" + "/seseorang"  # dirangkai: lihat catatan di test pola kredensial


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class SecretAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "t@example.invalid")
        _git(self.root, "config", "user.name", "t")
        self.write(".gitignore", CLEAN_GITIGNORE)
        self.write("README.md", "# contoh\n")
        self.track()

    def write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def track(self) -> None:
        _git(self.root, "add", "-A", "-f")

    def leaks(self) -> list[secret_audit.Finding]:
        return secret_audit.audit(self.root)[0]

    def notes(self) -> list[secret_audit.Finding]:
        return secret_audit.audit(self.root)[1]

    # --- dasar ---------------------------------------------------------
    def test_clean_repo_has_no_findings(self) -> None:
        self.assertEqual(self.leaks(), [])
        self.assertEqual(self.notes(), [])

    def test_surgeline_repo_itself_passes(self) -> None:
        leaks, _ = secret_audit.audit(REPO_ROOT)
        self.assertEqual([finding.line() for finding in leaks], [])

    # --- artefak runtime ter-track --------------------------------------
    def test_tracked_env_is_a_leak(self) -> None:
        self.write(".env", "SURGELINE_TARGET_PORT=8110\n")
        self.track()
        self.assertTrue(any(f.path == ".env" for f in self.leaks()))

    def test_env_example_is_allowed(self) -> None:
        self.write(".env.example", "SURGELINE_TARGET_PORT=8110\n")
        self.track()
        self.assertEqual(self.leaks(), [])

    def test_tracked_queue_db_is_a_leak(self) -> None:
        self.write("data/run/queue.db", "x")
        self.track()
        paths = {finding.path for finding in self.leaks()}
        self.assertIn("data/run/queue.db", paths)

    def test_tracked_report_is_a_leak(self) -> None:
        self.write("reports/REPORT.xlsx", "x")
        self.track()
        self.assertTrue(any(f.path == "reports/REPORT.xlsx" for f in self.leaks()))

    def test_sample_report_in_assets_is_allowed(self) -> None:
        self.write("assets/sample_REPORT.xlsx", "x")
        self.track()
        self.assertEqual(self.leaks(), [])

    def test_untracked_unignored_secret_is_a_leak(self) -> None:
        """`.gitignore` bolong + `.env` menganggur = ketahuan lewat `git status --short`,
        walau berkasnya belum pernah di-`git add`."""
        self.write(".gitignore", "reports/\nauth/\n*.db\n*.sqlite\n.venv/\ndata/\n")
        self.track()
        self.write(".env", "TOKEN=abc\n")
        leaks = self.leaks()
        self.assertTrue(
            any(finding.path == ".env" and finding.kind == "artefak" for finding in leaks),
            f"tidak tertangkap: {[f.line() for f in leaks]}",
        )

    # --- .gitignore ------------------------------------------------------
    def test_missing_gitignore_entry_is_a_leak(self) -> None:
        self.write(".gitignore", "data/\n")
        self.track()
        details = " ".join(finding.detail for finding in self.leaks())
        self.assertIn("*.db", details)

    def test_absent_gitignore_is_a_leak(self) -> None:
        (self.root / ".gitignore").unlink()
        _git(self.root, "rm", "-q", "--cached", ".gitignore")
        self.assertTrue(any(finding.kind == "gitignore" for finding in self.leaks()))

    # --- isi berkas ------------------------------------------------------
    def test_credential_patterns_are_leaks(self) -> None:
        # Contoh dirangkai saat berjalan, tidak ditulis utuh: kalau ditulis utuh,
        # berkas test ini sendiri jadi temuan `make audit` (dan itu pernah terjadi).
        samples = {
            "k_priv.txt": "-----BEGIN OPENSSH " + "PRIVATE KEY-----",
            "k_gh.txt": "ghp" + "_" + "a" * 36,
            "k_pat.txt": "github" + "_pat_" + "b" * 30,
            "k_sk.txt": "sk" + "-" + "c" * 32,
            "k_aws.txt": "AKIA" + "ABCDEFGHIJKLMNOP",
            "k_slack.txt": "xox" + "b-1234567890-abcdefghij",
            "k_pass.py": "%s = \"%s\"" % ("password", "sangat-rahasia-123"),
        }
        for name, text in samples.items():
            with self.subTest(name=name):
                self.write(name, text + "\n")
                self.track()
                self.assertTrue(
                    any(finding.path.startswith(name) for finding in self.leaks()),
                    f"{name} tidak tertangkap",
                )
                (self.root / name).unlink()
                _git(self.root, "rm", "-q", "--cached", name)

    def test_env_placeholder_is_not_a_secret(self) -> None:
        self.write("compose.yml", 'PASSWORD: "${DB_PASSWORD}"\n')
        self.track()
        self.assertEqual(self.leaks(), [])

    # --- jalur mesin -----------------------------------------------------
    def test_home_path_in_client_file_is_a_leak(self) -> None:
        self.write("README.md", "jalankan %s/Projects/x\n" % HOME_SAMPLE)
        self.track()
        self.assertTrue(any(finding.kind == "jalur" for finding in self.leaks()))

    def test_home_path_in_internal_doc_is_only_a_note(self) -> None:
        self.write("AGENTS.md", "script di %s/Projects/x\n" % HOME_SAMPLE)
        self.write("phases/phase-01.md", "lihat %s/Projects/y\n" % HOME_SAMPLE)
        self.track()
        self.assertEqual(self.leaks(), [])
        self.assertEqual(len(self.notes()), 2)

    # --- exit code -------------------------------------------------------
    def test_main_exit_codes(self) -> None:
        def code() -> int:
            with redirect_stdout(StringIO()):  # laporan audit tidak mengotori output test
                return secret_audit.main(["--root", str(self.root)])

        self.assertEqual(code(), 0)
        self.write(".env", "TOKEN=abc\n")
        self.track()
        self.assertEqual(code(), 1)


if __name__ == "__main__":
    unittest.main()
