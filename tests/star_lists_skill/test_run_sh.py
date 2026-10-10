"""run.sh: dependency checks, sign-in checks, and checksum-verified installs on a bare PATH.

Every test runs the script with a PATH holding only basic utilities and stubs,
so a gh or uv already installed on the machine running the tests cannot leak in.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from star_lists_skill.fakes import SCRIPTS

RUN_SH = SCRIPTS / "run.sh"
UTILITIES = (
    "sh",
    "sed",
    "tr",
    "grep",
    "cut",
    "head",
    "tar",
    "gzip",
    "mktemp",
    "cp",
    "chmod",
    "rm",
    "mkdir",
    "dirname",
    "basename",
    "cat",
    "sha256sum",
    "shasum",
    "perl",
    "openssl",
    "env",
)


def stub(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)


class RunShTests(unittest.TestCase):
    RUN_SH = RUN_SH

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in UTILITIES:
            found = shutil.which(name)
            if found:
                (self.bin / name).symlink_to(found)
        stub(self.bin / "uname", 'case "$1" in -s) echo Linux ;; -m) echo x86_64 ;; esac\n')
        self.tools = self.root / "tools"

    def with_python(self) -> None:
        (self.bin / "python3").symlink_to(sys.executable)

    def with_gh(self, authed: bool = True, scopes: str = "repo, user") -> None:
        stub(
            self.bin / "gh",
            f"""case "$1 $2" in
  "auth status") exit {0 if authed else 1} ;;
  "api user") echo octo ;;
  "api --include") printf 'HTTP/2.0 200 OK\\r\\nX-Oauth-Scopes: {scopes}\\r\\n\\r\\n{{}}' ;;
  "--version ") echo "gh version 9.9.9" ;;
  *) echo "unexpected gh $*" >&2; exit 3 ;;
esac
""",
        )

    def run_sh(self, *args: str) -> subprocess.CompletedProcess:
        env = {"PATH": str(self.bin), "HOME": str(self.root), "GITHUB_ACCOUNT_TOOLS_DIR": str(self.tools)}
        return subprocess.run(
            [str(self.bin / "sh"), str(self.RUN_SH), *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def test_doctor_passes_when_everything_is_present(self) -> None:
        self.with_python()
        self.with_gh()
        result = self.run_sh("doctor")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("signed in to github.com as octo", result.stdout)

    def test_the_tools_directory_star_lists_documented_is_still_used(self) -> None:
        self.with_python()
        legacy = self.root / "legacy"
        legacy.mkdir()
        stub(legacy / "gh", 'case "$1" in --version) echo "gh version 1.0.0" ;; *) exit 1 ;; esac\n')
        env = {"PATH": str(self.bin), "HOME": str(self.root), "STAR_LISTS_TOOLS_DIR": str(legacy)}
        result = subprocess.run(
            [str(self.bin / "sh"), str(self.RUN_SH), "doctor"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertIn("ok       gh       gh version 1.0.0", result.stdout)

    def test_doctor_names_the_fix_for_each_missing_piece(self) -> None:
        result = self.run_sh("doctor")
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing  python", result.stdout)
        self.assertIn("missing  gh", result.stdout)
        self.assertIn("doctor --install", result.stdout)

    def test_signed_out_gh_points_at_login(self) -> None:
        self.with_python()
        self.with_gh(authed=False)
        result = self.run_sh("doctor")
        self.assertEqual(result.returncode, 1)
        self.assertIn("gh auth login --hostname github.com --web --scopes user", result.stdout)
        result = self.run_sh("export")
        self.assertEqual(result.returncode, 1)
        self.assertIn("gh is not signed in", result.stderr)

    def test_token_without_user_scope_cannot_apply(self) -> None:
        self.with_python()
        self.with_gh(scopes="repo, read:org")
        doctor = self.run_sh("doctor")
        self.assertEqual(doctor.returncode, 1)
        self.assertIn("gh auth refresh --hostname github.com --scopes user", doctor.stdout)
        result = self.run_sh("apply", "plan.json", "--yes")
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot make these writes", result.stderr)
        self.assertIn("--scopes user", result.stderr)

    def test_fine_grained_token_without_scope_header_is_not_blocked(self) -> None:
        self.with_python()
        self.with_gh(scopes="")
        self.assertEqual(self.run_sh("doctor").returncode, 0)

    def test_commands_refuse_to_start_without_gh(self) -> None:
        self.with_python()
        result = self.run_sh("diff", "plan.json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("GitHub CLI is missing", result.stderr)

    def test_missing_downloader_names_a_package_command(self) -> None:
        self.with_python()
        stub(self.bin / "apt-get", "exit 0\n")
        result = self.run_sh("doctor", "--install")
        self.assertEqual(result.returncode, 1)
        self.assertIn("neither curl nor wget", result.stderr)
        self.assertIn("apt-get install -y curl", result.stderr)

    def release(self, corrupt: bool = False) -> Path:
        """Build a fake gh release and a curl stub that serves it from disk."""
        served = self.root / "served"
        folder = served / "gh_9.9.9_linux_amd64" / "bin"
        folder.mkdir(parents=True)
        stub(folder / "gh", 'echo "gh version 9.9.9"\n')
        archive = served / "gh_9.9.9_linux_amd64.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(served / "gh_9.9.9_linux_amd64", arcname="gh_9.9.9_linux_amd64")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if corrupt:
            digest = "0" * 64
        (served / "checksums.txt").write_text(f"{digest}  gh_9.9.9_linux_amd64.tar.gz\n")
        (served / "release.json").write_text('{\n  "tag_name": "v9.9.9",\n  "name": "GitHub CLI 9.9.9"\n}\n')
        stub(
            self.bin / "curl",
            f"""out=$5 url=$6
case $url in
  */releases/latest) src=release.json ;;
  *checksums.txt) src=checksums.txt ;;
  *.tar.gz) src=gh_9.9.9_linux_amd64.tar.gz ;;
  *) exit 22 ;;
esac
cp "{served}/$src" "$out"
""",
        )
        return served

    def test_install_fetches_gh_and_verifies_its_checksum(self) -> None:
        self.with_python()
        self.release()
        result = self.run_sh("doctor", "--install")
        self.assertIn("installed gh 9.9.9", result.stdout, result.stderr)
        self.assertTrue(os.access(self.tools / "gh", os.X_OK))
        self.assertIn("ok       gh       gh version 9.9.9", result.stdout)

    def test_install_refuses_a_checksum_mismatch(self) -> None:
        self.with_python()
        self.release(corrupt=True)
        result = self.run_sh("doctor", "--install")
        self.assertEqual(result.returncode, 1)
        self.assertIn("checksum mismatch", result.stderr)
        self.assertFalse((self.tools / "gh").exists())


if __name__ == "__main__":
    unittest.main()
