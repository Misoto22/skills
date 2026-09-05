"""The mirror driver and its hook registration, against forged stores on disk.

Four things this guards, each of which fails silently in a hook nobody watches:

- A watermark that does not advance. A PostToolUse hook fires on every tool call, so
  a mirror that re-reads from zero duplicates the whole conversation each time.
- A transcript written without its index entry. The desktop app lists conversations
  from its own index, so the mirror would exist and never appear — the exact failure
  the existing converters ship with.
- Registration that stacks or clobbers. Installing twice must replace, and neither
  install nor uninstall may disturb a hook somebody else put in the same file.
- A hook that reports failure. Its stdout is read as feedback by the agent that ran
  it and a non-zero exit can stop a turn, so `mirror` has to swallow everything.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins" / "dev" / "skills" / "handoff" / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load("formats")
handoff = _load("handoff")


class MirrorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.root = root
        handoff.STATE_PATH = root / "state.json"
        handoff.CODEX_SESSIONS = root / "codex"
        handoff.CLAUDE_PROJECTS = root / "projects"
        handoff.DESKTOP_SESSIONS = root / "desktop"
        handoff.DESKTOP_CONFIG = root / "config.json"
        (root / "desktop" / "acct" / "org").mkdir(parents=True)
        (root / "config.json").write_text(json.dumps({"lastKnownAccountUuid": "acct"}))
        self.addCleanup(self._tmp.cleanup)

    def _append(self, path: Path, records):
        with open(path, "a") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")

    def test_a_second_firing_mirrors_only_what_is_new(self):
        """The failure this prevents, asserted on real output."""
        source = self.root / "transcript.jsonl"
        payload = {"transcript_path": str(source), "session_id": "s1", "cwd": "/tmp/proj"}
        self._append(source, [{"type": "user", "message": {"role": "user", "content": "one"}}])
        state = handoff.load_state()
        handoff.mirror_from_claude(payload, state)
        self._append(source, [{"type": "user", "message": {"role": "user", "content": "two"}}])
        handoff.mirror_from_claude(payload, state)
        self.assertEqual("nothing new", handoff.mirror_from_claude(payload, state))

        rollouts = list((self.root / "codex").rglob("rollout-*.jsonl"))
        self.assertEqual(len(rollouts), 1)
        lines = [json.loads(line) for line in rollouts[0].read_text().splitlines()]
        self.assertEqual(lines[0]["type"], "session_meta")
        texts = [
            item["payload"]["content"][0]["text"] for item in lines[1:] if item["type"] == "response_item"
        ]
        self.assertEqual(texts, ["one", "two"])

    def test_the_claude_mirror_is_written_into_the_sidebar_index(self):
        source = self.root / "rollout.jsonl"
        self._append(
            source,
            [
                {
                    "type": "response_item",
                    "payload": {"type": "message", "role": "assistant", "content": [{"text": "hello"}]},
                }
            ],
        )
        state = handoff.load_state()
        handoff.mirror_from_codex({"rollout_path": str(source), "cwd": "/tmp/proj"}, state)

        entries = list((self.root / "desktop").rglob("local_*.json"))
        self.assertEqual(len(entries), 1)
        entry = json.loads(entries[0].read_text())
        transcript = self.root / "projects" / handoff.slug_for("/tmp/proj") / f"{entry['cliSessionId']}.jsonl"
        self.assertTrue(transcript.is_file(), "the index entry must point at a transcript that exists")
        self.assertFalse(entry["isArchived"])

    def test_a_missing_transcript_is_reported_rather_than_raised(self):
        state = handoff.load_state()
        note = handoff.mirror_from_claude({"transcript_path": "/nope.jsonl", "session_id": "s"}, state)
        self.assertIn("no transcript", note)


class RegisterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config = Path(self._tmp.name) / "settings.json"
        self.config.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": [{"hooks": [{"type": "command", "command": "afplay Glass.aiff"}]}],
                        "PreToolUse": [
                            {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}
                        ],
                    }
                }
            )
        )
        self.runner = Path(self._tmp.name) / "handoff" / "handoff.py"
        self.addCleanup(self._tmp.cleanup)

    def _hooks(self):
        return json.loads(self.config.read_text())["hooks"]

    def _install(self):
        return handoff.register(self.config, "claude", remove=False, runner=self.runner)

    def test_installing_leaves_other_peoples_hooks_alone(self):
        self._install()
        hooks = self._hooks()
        self.assertIn("Glass.aiff", json.dumps(hooks["Stop"]))
        self.assertEqual(hooks["PreToolUse"][0]["hooks"][0]["command"], "echo hi")
        self.assertEqual(len(hooks["Stop"]), 2)

    def test_installing_twice_replaces_rather_than_stacks(self):
        self._install()
        self._install()
        self.assertEqual(len(self._hooks()["Stop"]), 2)

    def test_uninstall_removes_only_this_skills_entries(self):
        self._install()
        handoff.register(self.config, "claude", remove=True)
        hooks = self._hooks()
        self.assertEqual(len(hooks["Stop"]), 1)
        self.assertIn("Glass.aiff", json.dumps(hooks["Stop"]))
        self.assertNotIn("PostToolUse", hooks)
        self.assertIn("PreToolUse", hooks)

    def test_uninstall_claims_an_entry_left_by_an_older_plugin_version(self):
        """A path-based match would strand one stale hook per plugin release."""
        stale = {
            "hooks": [
                {
                    "type": "command",
                    "command": "python3 /cache/dev/0.15.0/skills/handoff/scripts/handoff.py "
                    "mirror --from=claude >/dev/null 2>&1 || true",
                }
            ]
        }
        data = json.loads(self.config.read_text())
        data["hooks"]["PostToolUse"] = [stale]
        self.config.write_text(json.dumps(data))
        handoff.register(self.config, "claude", remove=True)
        self.assertNotIn("PostToolUse", self._hooks())

    def test_a_config_that_is_not_json_is_left_untouched(self):
        self.config.write_text("{not json")
        note = self._install()
        self.assertIn("left alone", note)
        self.assertEqual(self.config.read_text(), "{not json")


if __name__ == "__main__":
    unittest.main()
