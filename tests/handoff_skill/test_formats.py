"""The Claude/Codex field-name translation, exercised on both real shapes.

The mapping table in SKILL.md is prose; these are the parts of it that fail silently
when they are wrong. A tool call whose arguments arrive as the string Codex sends,
rather than the object Claude expects, still renders — as a tool nobody can read. A
linked list whose second batch does not name the first leaves the transcript looking
complete while the app shows only the tail. And a partial final line, which every
hook meets because it fires mid-write, must be read whole on the next pass rather
than dropped.
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


formats = _load("formats")


CLAUDE_TURN = [
    {"type": "user", "message": {"role": "user", "content": "run the tests"}},
    {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "check for a test command", "signature": "sig"},
                {"type": "text", "text": "Running them."},
                {"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {"command": "pytest -q"}},
            ],
        },
    },
    {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "content": [{"type": "text", "text": "3 passed"}]}
            ],
        },
    },
]


class ClaudeToCodexTests(unittest.TestCase):
    def test_every_block_maps_to_its_codex_counterpart(self):
        """The failure this prevents, asserted on real output."""
        items = [line["payload"]["type"] for line in formats.claude_to_codex(CLAUDE_TURN, "t1")]
        self.assertEqual(
            items, ["message", "reasoning", "message", "function_call", "function_call_output"]
        )

    def test_tool_arguments_travel_as_the_json_string_codex_reads(self):
        call = next(
            line["payload"]
            for line in formats.claude_to_codex(CLAUDE_TURN, "t1")
            if line["payload"]["type"] == "function_call"
        )
        self.assertEqual(call["name"], "Bash")
        self.assertEqual(json.loads(call["arguments"]), {"command": "pytest -q"})
        self.assertEqual(call["call_id"], "toolu_1")

    def test_the_turn_id_reaches_every_item(self):
        for line in formats.claude_to_codex(CLAUDE_TURN, "t9"):
            passthrough = line["payload"]["internal_chat_message_metadata_passthrough"]
            self.assertEqual(passthrough["turn_id"], "t9")


class CodexToClaudeTests(unittest.TestCase):
    def test_round_trip_keeps_the_tool_call_readable(self):
        rollout = list(formats.claude_to_codex(CLAUDE_TURN, "t1"))
        lines, _ = formats.codex_to_claude(rollout, session_id="s", cwd="/tmp", parent=None)
        uses = [b for line in lines for b in line["message"]["content"] if b["type"] == "tool_use"]
        results = [b for line in lines for b in line["message"]["content"] if b["type"] == "tool_result"]
        self.assertEqual([u["name"] for u in uses], ["Bash"])
        self.assertEqual([u["input"] for u in uses], [{"command": "pytest -q"}])
        self.assertEqual([r["content"] for r in results], ["3 passed"])

    def test_the_linked_list_survives_a_second_batch(self):
        """Two hook firings must produce one chain, not two."""
        rollout = list(formats.claude_to_codex(CLAUDE_TURN, "t1"))
        first, tail = formats.codex_to_claude(rollout[:2], session_id="s", cwd="/tmp", parent=None)
        second, _ = formats.codex_to_claude(rollout[2:], session_id="s", cwd="/tmp", parent=tail)
        chain = first + second
        self.assertIsNone(chain[0]["parentUuid"])
        for earlier, later in zip(chain, chain[1:]):
            self.assertEqual(later["parentUuid"], earlier["uuid"])

    def test_codex_own_prompt_is_not_mistaken_for_the_conversation(self):
        developer = [
            {
                "type": "response_item",
                "payload": {"type": "message", "role": "developer", "content": [{"text": "system"}]},
            }
        ]
        lines, tail = formats.codex_to_claude(developer, session_id="s", cwd="/tmp", parent=None)
        self.assertEqual(lines, [])
        self.assertIsNone(tail)

    def test_unreadable_reasoning_is_dropped_rather_than_forged(self):
        encrypted = [
            {"type": "response_item", "payload": {"type": "reasoning", "summary": [], "encrypted_content": "x"}}
        ]
        lines, _ = formats.codex_to_claude(encrypted, session_id="s", cwd="/tmp", parent=None)
        self.assertEqual(lines, [])

    def test_a_string_argument_that_is_not_json_still_reaches_the_reader(self):
        call = [
            {
                "type": "response_item",
                "payload": {"type": "custom_tool_call", "call_id": "c1", "name": "exec", "input": "not json"},
            }
        ]
        lines, _ = formats.codex_to_claude(call, session_id="s", cwd="/tmp", parent=None)
        self.assertEqual(lines[0]["message"]["content"][0]["input"], {"raw": "not json"})


class ReadJsonlTests(unittest.TestCase):
    def test_a_half_written_final_line_is_left_for_the_next_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            path.write_text('{"a": 1}\n{"b": 2}\n{"c": ')
            records, offset = formats.read_jsonl(path)
            self.assertEqual(records, [{"a": 1}, {"b": 2}])
            path.write_text('{"a": 1}\n{"b": 2}\n{"c": 3}\n')
            more, _ = formats.read_jsonl(path, offset)
            self.assertEqual(more, [{"c": 3}])

    def test_a_file_with_no_newline_yet_advances_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            path.write_text('{"a": ')
            self.assertEqual(formats.read_jsonl(path), ([], 0))


if __name__ == "__main__":
    unittest.main()
