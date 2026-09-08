#!/usr/bin/env python3
"""Verify that an installed dev plugin emits Codex's current-task title instruction.

Usage:
  python3 scripts/verify-codex-retitle.py <installed-dev-plugin-root>

This is an artifact-bound smoke test, not a desktop E2E test. It invokes the installed
``UserPromptSubmit`` hook with a Codex-shaped event and checks the emitted instruction
uses Codex's native current-task call rather than Claude Code's session identifier.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path("skills/retitle/assets/session-naming-hook.py")
CODEX_MANIFEST = Path(".codex-plugin/plugin.json")
HOOK_CONFIG = "./hooks/hooks.json"
CODEX_TITLE_TOOL = "mcp__codex_app__set_thread_title"
CLAUDE_TITLE_TOOL = "mcp__ccd_session_mgmt__set_session_title"
CURRENT_TASK_WORDING = "Pass title and omit `threadId`"


def installed_hook(install_root: Path) -> tuple[Path | None, list[str]]:
    """Locate the one retitle hook below a plugin root or marketplace cache."""
    resolved_root = install_root.expanduser().resolve()
    direct = resolved_root / HOOK
    if direct.is_file():
        return direct, []
    hooks = sorted(set(resolved_root.glob(f"*/{HOOK}")) | set(resolved_root.glob(f"*/*/{HOOK}")))
    if len(hooks) == 1:
        return hooks[0], []
    if not hooks:
        return None, [f"no installed retitle hook below {resolved_root}"]
    return None, [f"more than one installed retitle hook below {resolved_root}"]


def verify(install_root: Path) -> list[str]:
    """Return installed-artifact errors, or an empty list when the Codex hook is sound."""
    hook, errors = installed_hook(install_root)
    if hook is None:
        return errors
    manifest_path = hook.parents[3] / CODEX_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return [f"cannot read installed Codex plugin manifest {manifest_path}: {error}"]
    if manifest.get("hooks") != HOOK_CONFIG:
        return [f"{manifest_path} must declare hooks as {HOOK_CONFIG!r}"]

    with tempfile.TemporaryDirectory() as data_directory:
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PLUGIN_ROOT": str(hook.parents[3]),
            "CLAUDE_PLUGIN_DATA": data_directory,
        }
        result = subprocess.run(
            [sys.executable, str(hook)],
            input=json.dumps({"session_id": "installed-codex-smoke", "turn_id": "turn-1"}),
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )
    if result.returncode != 0:
        return [f"installed retitle hook exited {result.returncode}: {result.stderr.strip()}"]
    try:
        output = json.loads(result.stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        return [f"installed retitle hook emitted no usable UserPromptSubmit context: {error}"]
    if not isinstance(context, str):
        return ["installed retitle hook emitted a non-text additionalContext"]
    errors: list[str] = []
    if CODEX_TITLE_TOOL not in context:
        errors.append(f"Codex context does not name {CODEX_TITLE_TOOL}")
    if CURRENT_TASK_WORDING not in context:
        errors.append("Codex context does not say that threadId must be omitted")
    if CLAUDE_TITLE_TOOL in context:
        errors.append("Codex context incorrectly names Claude Code's session-title tool")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("install_root", type=Path)
    args = parser.parse_args()
    errors = verify(args.install_root)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Codex retitle hook verified: {args.install_root.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
