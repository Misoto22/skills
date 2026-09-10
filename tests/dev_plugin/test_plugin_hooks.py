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
CODEX_MANIFEST = PLUGIN / ".codex-plugin" / "plugin.json"
SESSION_HOOK = PLUGIN / "skills" / "retitle" / "assets" / "session-naming-hook.py"
ORCHESTRATE_HOOK = PLUGIN / "hooks" / "orchestrate.py"
AGENTS = PLUGIN / "agents"
# A plugin subagent is a frontmatter file. These four fields are what one may declare;
# `hooks`, `mcpServers` and `permissionMode` belong to a settings file and are dropped here.
AGENT_FIELDS = ("name", "description", "tools", "model")
FORBIDDEN_AGENT_FIELDS = ("hooks", "mcpServers", "permissionMode")
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


def _frontmatter(path: Path) -> dict[str, str]:
    """The agent file's leading `---` block as plain key/value pairs, as the loader reads it."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    return fields


class DevPluginHookTests(unittest.TestCase):
    def test_codex_manifest_discovers_the_plugin_hook_file(self) -> None:
        """Codex needs its native manifest before it loads a plugin's hook directory."""
        manifest = json.loads(CODEX_MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "dev")
        self.assertEqual(manifest["hooks"], "./hooks/hooks.json")

    def test_both_prompt_hooks_are_registered_on_prompt_submit(self) -> None:
        manifest = json.loads(HOOKS.read_text(encoding="utf-8"))
        self.assertEqual(list(manifest), ["hooks"])
        commands = [
            hook["command"] for group in manifest["hooks"]["UserPromptSubmit"] for hook in group["hooks"]
        ]
        self.assertEqual(len(commands), 2)
        registered = " ".join(commands)
        self.assertIn(SESSION_HOOK.relative_to(PLUGIN).as_posix(), registered)
        self.assertIn(ORCHESTRATE_HOOK.relative_to(PLUGIN).as_posix(), registered)

    def test_the_orchestrate_hook_matches_every_tool_that_can_write(self) -> None:
        """A matcher short of one write tool leaves the orchestrator one habit to fall back on."""
        manifest = json.loads(HOOKS.read_text(encoding="utf-8"))
        relative = ORCHESTRATE_HOOK.relative_to(PLUGIN).as_posix()
        matchers = [
            group.get("matcher", "")
            for group in manifest["hooks"]["PreToolUse"]
            if any(relative in hook["command"] for hook in group["hooks"])
        ]

        self.assertEqual(len(matchers), 1)
        # `apply_patch` is how Codex reports a file edit; without it the hook never sees one.
        for tool in ("Edit", "Write", "MultiEdit", "NotebookEdit", "Bash", "apply_patch"):
            with self.subTest(tool=tool):
                self.assertTrue(re.fullmatch(matchers[0], tool), f"{tool} is not matched")

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
        self.assertIn("orchestrator_models", options)
        sources = [SESSION_HOOK.read_text(encoding="utf-8")]
        sources += [path.read_text(encoding="utf-8") for path in sorted((PLUGIN / "hooks").glob("*.py"))]
        for key, option in options.items():
            with self.subTest(option=key):
                for field in ("type", "title", "description"):
                    self.assertIn(field, option)
                variable = f"CLAUDE_PLUGIN_OPTION_{key.upper()}"
                self.assertTrue(
                    any(variable in source for source in sources),
                    f"no shipped hook reads {variable}",
                )

    def test_every_agent_declares_what_a_plugin_subagent_may_declare(self) -> None:
        """A plugin subagent that carries a settings-file field is refused as a whole."""
        agents = sorted(AGENTS.glob("*.md"))
        self.assertTrue(agents, "the dev plugin ships no agents")
        for agent in agents:
            with self.subTest(agent=agent.name):
                fields = _frontmatter(agent)
                for required in ("name", "description", "model"):
                    self.assertIn(required, fields)
                self.assertEqual(fields["name"], agent.stem)
                for forbidden in FORBIDDEN_AGENT_FIELDS:
                    self.assertNotIn(forbidden, fields)
                self.assertTrue(set(fields) <= set(AGENT_FIELDS), f"unknown field in {agent.name}")


if __name__ == "__main__":
    unittest.main()
