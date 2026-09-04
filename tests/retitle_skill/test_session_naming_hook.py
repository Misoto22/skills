"""The shipped session-naming hook, exercised the way Claude Code runs it.

Two failures this prevents, both found by hand before the hook was published:

- A cadence regression. The hook fires the full rule once and a short re-check every
  fifth prompt. Get the modulo wrong and it either nags every turn or never re-checks,
  and neither is visible until someone counts messages in a live session.
- A crash on a marker it did not write. The earlier shell version left empty marker
  files behind; under `set -euo pipefail` reading one aborted the hook, which blocks
  the user's prompt. Every failure path here has to stay silent and exit 0.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "plugins" / "dev" / "skills" / "retitle" / "assets" / "session-naming-hook.py"


class SessionNamingHookTests(unittest.TestCase):
    """Drive the hook as a subprocess, because that is the only way it is ever run."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.config = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def run_hook(self, session_id: str, *, every: str | None = None) -> str:
        env = {"HOME": str(self.config), "CLAUDE_CONFIG_DIR": str(self.config), "PATH": "/usr/bin:/bin"}
        if every is not None:
            env["SESSION_TITLE_RECHECK_EVERY"] = every
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps({"session_id": session_id}),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    @staticmethod
    def kind(stdout: str) -> str:
        if not stdout.strip():
            return "silent"
        context = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
        if "Session naming rule" in context:
            return "full"
        return "recheck" if "Title re-check" in context else "unknown"

    def markers(self) -> Path:
        return self.config / ".session-naming-markers"

    def test_full_rule_then_a_recheck_every_fifth_prompt(self) -> None:
        got = [self.kind(self.run_hook("cadence")) for _ in range(12)]
        self.assertEqual(
            got,
            ["full"] + ["silent"] * 4 + ["recheck"] + ["silent"] * 4 + ["recheck", "silent"],
        )

    def test_zero_disables_the_recheck(self) -> None:
        got = [self.kind(self.run_hook("once", every="0")) for _ in range(7)]
        self.assertEqual(got, ["full"] + ["silent"] * 6)

    def test_the_reminder_carries_the_scheme_and_todays_date(self) -> None:
        context = json.loads(self.run_hook("scheme"))["hookSpecificOutput"]["additionalContext"]
        # Written as the codepoint: the assertion is that the fullwidth separator
        # survives, and an ASCII pipe here would pass against a broken hook.
        self.assertIn("MMDD\uff5c类型\uff5c主题", context)
        self.assertIn("U+FF5C", context)
        for kind in ("功能", "设计", "修复", "优化", "发布", "探索", "文档", "研究"):
            self.assertIn(kind, context)

    def test_an_empty_marker_from_the_shell_version_upgrades_in_place(self) -> None:
        self.run_hook("upgrade")
        marker = next(self.markers().iterdir())
        marker.write_text("", encoding="utf-8")
        self.assertEqual(self.kind(self.run_hook("upgrade")), "full")
        self.assertEqual(marker.read_text(encoding="utf-8"), "1")

    def test_a_corrupt_marker_resets_rather_than_raising(self) -> None:
        self.run_hook("corrupt")
        marker = next(self.markers().iterdir())
        marker.write_text("not-a-number", encoding="utf-8")
        self.assertEqual(self.kind(self.run_hook("corrupt")), "full")
        self.assertEqual(marker.read_text(encoding="utf-8"), "1")

    def test_an_event_without_a_session_stays_silent(self) -> None:
        for payload in ("", "{}", "not json", "[]", '{"session_id": ""}'):
            with self.subTest(payload=payload):
                result = subprocess.run(
                    [sys.executable, str(HOOK)],
                    input=payload,
                    capture_output=True,
                    text=True,
                    env={"HOME": str(self.config), "PATH": "/usr/bin:/bin"},
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "")

    def test_a_session_id_never_escapes_the_marker_directory(self) -> None:
        self.run_hook("../../etc/passwd")
        written = list(self.markers().iterdir())
        self.assertEqual(len(written), 1)
        self.assertNotIn("/", written[0].name)


if __name__ == "__main__":
    unittest.main()
