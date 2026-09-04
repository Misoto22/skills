"""The shipped session-naming hook, exercised the way Claude Code runs it.

Two failures this prevents, both found by hand before the hook was published:

- A cadence regression. The hook fires the full rule once and a short re-check every
  fifth prompt. Get the modulo wrong and it either nags every turn or never re-checks,
  and neither is visible until someone counts messages in a live session.
- A crash on a marker it did not write. The earlier shell version left empty marker
  files behind; under `set -euo pipefail` reading one aborted the hook, which blocks
  the user's prompt. Every failure path here has to stay silent and exit 0.
- A widened type. The English types are five uppercase letters so that the subject
  starts at nearly the same place on every row; a natural-word set is twice as ragged
  (DESIGN against FIX) and the column stops reading as a column. Nothing in the rule
  text says so out loud, which is exactly why it needs asserting.
"""

from __future__ import annotations

import datetime as dt
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

    def run_hook(
        self,
        session_id: str,
        *,
        every: str | None = None,
        transcript: str | None = None,
        lang: str | None = None,
        env_extra: dict[str, str] | None = None,
        event_extra: dict[str, str] | None = None,
    ) -> str:
        env = {"HOME": str(self.config), "CLAUDE_CONFIG_DIR": str(self.config), "PATH": "/usr/bin:/bin"}
        if every is not None:
            env["SESSION_TITLE_RECHECK_EVERY"] = every
        if lang is not None:
            env["SESSION_TITLE_LANG"] = lang
        env.update(env_extra or {})
        event = {"session_id": session_id, **(event_extra or {})}
        if transcript is not None:
            event["transcript_path"] = transcript
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(event),
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

    @staticmethod
    def types(context: str, label: str) -> list[str]:
        """The type vocabulary as the shipped hook actually spells it, not as a test repeats it."""
        prefix = f"- {label}: exactly one of "
        line = next(line for line in context.splitlines() if line.startswith(prefix))
        return line.removeprefix(prefix).split(" — ")[0].split(", ")

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

    def test_the_reminder_carries_the_english_scheme_by_default(self) -> None:
        context = json.loads(self.run_hook("scheme"))["hookSpecificOutput"]["additionalContext"]
        # Written as the codepoint: the assertion is that the fullwidth separator
        # survives, and an ASCII pipe here would pass against a broken hook.
        self.assertIn("MMDD\uff5cTYPE\uff5csubject", context)
        self.assertIn("U+FF5C", context)
        for kind in ("BUILD", "SHAPE", "PATCH", "TWEAK", "SHIP", "PROBE", "WRITE", "AUDIT", "STUDY"):
            self.assertIn(kind, context)
        # AUDIT collapses into STUDY unless the reminder carries what separates them.
        self.assertIn("The line is the object", context)

    def test_every_english_type_holds_the_column_width(self) -> None:
        # Two CJK characters are a fixed em each, so the Chinese type field never moves
        # the subject. English in a proportional font cannot match that, so the scheme
        # fixes the letter count instead — and SHIP is the single member allowed to be
        # short, because no honest five-letter verb covers commit/PR/tag/deploy/publish.
        context = json.loads(self.run_hook("width"))["hookSpecificOutput"]["additionalContext"]
        kinds = self.types(context, "TYPE")
        self.assertEqual(len(kinds), 9, kinds)
        for kind in kinds:
            with self.subTest(kind=kind):
                self.assertTrue(kind.isupper(), kind)
                self.assertEqual(len(kind), 4 if kind == "SHIP" else 5, kind)

    def test_the_chinese_scheme_is_opt_in(self) -> None:
        context = json.loads(self.run_hook("chinese", lang="zh"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("MMDD\uff5c类型\uff5c主题", context)
        self.assertNotIn("MMDD\uff5cTYPE\uff5csubject", context)
        self.assertEqual(
            self.types(context, "类型"),
            ["功能", "设计", "修复", "优化", "发布", "探索", "文档", "审计", "研究"],
        )

    def test_a_locale_tag_still_selects_chinese(self) -> None:
        # Someone reaching for a language setting writes the locale they know, and
        # `zh-CN` silently falling back to English is a setting that looks applied.
        for tag in ("zh-CN", "zh_Hans", "ZH"):
            with self.subTest(tag=tag):
                context = json.loads(self.run_hook(f"locale-{tag}", lang=tag))["hookSpecificOutput"][
                    "additionalContext"
                ]
                self.assertIn("MMDD\uff5c类型\uff5c主题", context)

    def test_an_unknown_language_falls_back_to_english(self) -> None:
        # A rule in the wrong language still names the session; refusing to emit one
        # trades a misspelled locale for the whole feature.
        context = json.loads(self.run_hook("unknown", lang="klingon"))["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertIn("MMDD\uff5cTYPE\uff5csubject", context)

    def test_the_recheck_follows_the_chosen_language(self) -> None:
        # The re-check names the fields it wants changed. In Chinese those fields are
        # 类型 and 主题; leaving that half English is how a session drifts back to the
        # default vocabulary five prompts in.
        for _ in range(5):
            self.run_hook("chinese-recheck", lang="zh")
        context = json.loads(self.run_hook("chinese-recheck", lang="zh"))["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertIn("Title re-check", context)
        self.assertIn("change 类型 and 主题", context)
        self.assertNotIn("TYPE and subject", context)

    def test_both_reminders_name_the_session_argument(self) -> None:
        # `set_session_title` requires `session_id`, and only the literal "self" reaches
        # the running session. A reminder that omits it costs the model a validation
        # error, then a guess at the id in its own transcript path — which answers
        # "not found", so the session keeps whatever title the client generated.
        first = self.run_hook("argument")
        self.assertEqual(self.kind(first), "full")
        self.assertIn('session_id: "self"', json.loads(first)["hookSpecificOutput"]["additionalContext"])
        for _ in range(4):
            self.run_hook("argument")
        sixth = self.run_hook("argument")
        self.assertEqual(self.kind(sixth), "recheck")
        self.assertIn('session_id: "self"', json.loads(sixth)["hookSpecificOutput"]["additionalContext"])

    def write_transcript(self, first_timestamp: str) -> str:
        path = self.config / "transcript.jsonl"
        path.write_text(json.dumps({"timestamp": first_timestamp, "type": "user"}) + "\n", encoding="utf-8")
        return str(path)

    def test_the_date_comes_from_the_session_not_from_today(self) -> None:
        # A re-check days later, or a session running past midnight, must not move the
        # date — it is the only thing the sidebar orders by.
        transcript = self.write_transcript("2026-08-13T22:15:00.000Z")
        context = json.loads(self.run_hook("dated", transcript=transcript))["hookSpecificOutput"][
            "additionalContext"
        ]
        expected = dt.datetime.fromisoformat("2026-08-13T22:15:00.000+00:00").astimezone().strftime("%m%d")
        self.assertIn(f"MMDD is {expected}", context)
        self.assertNotIn(f"MMDD is {dt.datetime.now().strftime('%m%d')}", context.replace(expected, ""))

    def test_the_recheck_carries_the_same_session_date(self) -> None:
        transcript = self.write_transcript("2026-08-13T22:15:00.000Z")
        expected = dt.datetime.fromisoformat("2026-08-13T22:15:00.000+00:00").astimezone().strftime("%m%d")
        for _ in range(5):
            self.run_hook("dated-recheck", transcript=transcript)
        context = json.loads(self.run_hook("dated-recheck", transcript=transcript))["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertIn("Title re-check", context)
        self.assertIn(f"keep MMDD as {expected}", context)

    def test_an_unreadable_transcript_falls_back_to_today(self) -> None:
        context = json.loads(self.run_hook("nodate", transcript="/nonexistent/transcript.jsonl"))[
            "hookSpecificOutput"
        ]["additionalContext"]
        self.assertIn(f"MMDD is {dt.datetime.now().strftime('%m%d')}", context)

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

    def test_the_plugin_option_selects_chinese(self) -> None:
        """Claude Code hands a plugin hook its `session_title_lang` option as an environment variable."""
        out = self.run_hook("s1", env_extra={"CLAUDE_PLUGIN_OPTION_SESSION_TITLE_LANG": "zh"})
        context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("MMDD｜类型｜主题", context)  # noqa: RUF001

    def test_an_explicit_variable_beats_the_plugin_option(self) -> None:
        """A machine that set SESSION_TITLE_LANG before the option existed keeps naming as it did."""
        out = self.run_hook("s1", lang="en", env_extra={"CLAUDE_PLUGIN_OPTION_SESSION_TITLE_LANG": "zh"})
        context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("MMDD｜TYPE｜subject", context)  # noqa: RUF001

    def test_a_codex_plugin_hook_stays_silent(self) -> None:
        """Codex runs the same plugin hook but has no tool the rule could name."""
        out = self.run_hook("s1", env_extra={"PLUGIN_ROOT": "/plugins/dev"}, event_extra={"turn_id": "t1"})
        self.assertEqual(self.kind(out), "silent")
        self.assertFalse(self.markers().exists())

    def test_a_codex_shaped_event_stays_silent_without_plugin_variables(self) -> None:
        out = self.run_hook("s1", event_extra={"turn_id": "t1"})
        self.assertEqual(self.kind(out), "silent")

    def test_claude_code_fires_even_when_codex_variables_leak_in(self) -> None:
        """A Claude Code session started from a shell that exports PLUGIN_ROOT is still Claude Code."""
        out = self.run_hook(
            "s1",
            env_extra={"CLAUDECODE": "1", "PLUGIN_ROOT": "/plugins/dev"},
            event_extra={"prompt_id": "p1"},
        )
        self.assertEqual(self.kind(out), "full")

    def test_markers_live_in_the_plugin_data_directory_when_there_is_one(self) -> None:
        """CLAUDE_PLUGIN_DATA survives plugin updates; the config directory is the hand-installed home."""
        data = self.config / "data"
        self.run_hook("s1", env_extra={"CLAUDE_PLUGIN_DATA": str(data)})
        self.assertEqual([p.name for p in (data / "session-naming-markers").iterdir()], ["s1"])
        self.assertFalse(self.markers().exists())


if __name__ == "__main__":
    unittest.main()
