"""The hooks the dev plugin registers on install, held to the files they run.

A plugin hook is registered the moment the plugin is enabled and runs on every
prompt, so a command pointing at a path that moved fails silently on every
machine at once. The manifest's `userConfig` is the other half: an option the
hook never reads is a setting that does nothing.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "dev"
HOOKS = PLUGIN / "hooks" / "hooks.json"
MANIFEST = PLUGIN / ".claude-plugin" / "plugin.json"
SESSION_HOOK = PLUGIN / "skills" / "retitle" / "assets" / "session-naming-hook.py"
PLUGIN_ROOT_PATH = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"' ]+)")


def _commands() -> list[str]:
    manifest = json.loads(HOOKS.read_text(encoding="utf-8"))
    return [
        hook["command"]
        for event in manifest["hooks"].values()
        for group in event
        for hook in group["hooks"]
        if hook.get("type") == "command"
    ]


class DevPluginHookTests(unittest.TestCase):
    def test_the_session_naming_hook_is_registered_on_prompt_submit(self) -> None:
        manifest = json.loads(HOOKS.read_text(encoding="utf-8"))
        self.assertEqual(list(manifest), ["hooks"])
        commands = [
            hook["command"] for group in manifest["hooks"]["UserPromptSubmit"] for hook in group["hooks"]
        ]
        self.assertEqual(len(commands), 1)
        self.assertIn(SESSION_HOOK.relative_to(PLUGIN).as_posix(), commands[0])

    def test_every_command_runs_a_file_the_plugin_ships(self) -> None:
        for command in _commands():
            paths = PLUGIN_ROOT_PATH.findall(command)
            self.assertTrue(paths, f"a plugin hook must resolve from the plugin root: {command}")
            for relative in paths:
                with self.subTest(path=relative):
                    self.assertTrue((PLUGIN / relative).is_file(), f"{relative} is not shipped by the plugin")
                    self.assertNotIn("..", relative)

    def test_a_command_names_no_machine(self) -> None:
        text = HOOKS.read_text(encoding="utf-8")
        for fragment in ("/Users/", "/home/", "~/"):
            self.assertNotIn(fragment, text)

    def test_every_option_reaches_the_hook_that_reads_it(self) -> None:
        options = json.loads(MANIFEST.read_text(encoding="utf-8")).get("userConfig", {})
        self.assertIn("session_title_lang", options)
        source = SESSION_HOOK.read_text(encoding="utf-8")
        for key, option in options.items():
            with self.subTest(option=key):
                for field in ("type", "title", "description"):
                    self.assertIn(field, option)
                self.assertIn(f"CLAUDE_PLUGIN_OPTION_{key.upper()}", source)


if __name__ == "__main__":
    unittest.main()
