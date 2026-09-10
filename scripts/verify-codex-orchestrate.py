#!/usr/bin/env python3
"""Verify that an installed dev plugin refuses a project edit on a Codex orchestrator model.

Usage:
  python3 scripts/verify-codex-orchestrate.py <installed-dev-plugin-root>

This is an artifact-bound smoke test, not a desktop E2E test. Codex is the client with no
`agent_id` and no transcript to read, so the active model on the event is the only signal
it has: this invokes the installed ``PreToolUse`` hook with Codex-shaped events and checks
that an orchestrator model is refused and a cheaper one is left alone.

The events are the shapes Codex actually sends. A file edit arrives as
``tool_name: "apply_patch"`` with the patch body — not a path — in ``tool_input.command``,
which is the form a hook keyed on ``Edit`` would walk straight past; the shell form is
sent as well, because ``sed -i`` is the habit the guardrail exists to catch.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path("hooks/orchestrate.py")
CODEX_MANIFEST = Path(".codex-plugin/plugin.json")
HOOK_CONFIG = "./hooks/hooks.json"
ORCHESTRATOR_MODEL = "gpt-6-astra"
CHEAP_MODEL = "gpt-5.6-luna"
CLAUDE_AGENT = "dev:implementer"
EDITED_PATH = "src/app.py"
PATCH_BODY = (
    "*** Begin Patch\n"
    f"*** Update File: {EDITED_PATH}\n"
    "@@ def main():\n"
    "-    return 0\n"
    "+    return 1\n"
    "*** End Patch\n"
)
SHELL_EDIT = f"sed -i 's/a/b/' {EDITED_PATH}"


def installed_hook(install_root: Path) -> tuple[Path | None, list[str]]:
    """Locate the one orchestrate hook below a plugin root or marketplace cache."""
    resolved_root = install_root.expanduser().resolve()
    direct = resolved_root / HOOK
    if direct.is_file():
        return direct, []
    hooks = sorted(set(resolved_root.glob(f"*/{HOOK}")) | set(resolved_root.glob(f"*/*/{HOOK}")))
    if len(hooks) == 1:
        return hooks[0], []
    if not hooks:
        return None, [f"no installed orchestrate hook below {resolved_root}"]
    return None, [f"more than one installed orchestrate hook below {resolved_root}"]


def _run(hook: Path, model: str, project: str, tool: str, command: str) -> subprocess.CompletedProcess[str]:
    """Invoke the hook the way Codex does: PLUGIN_ROOT set, the model on the event.

    Both of Codex's write tools put their payload in ``tool_input.command`` — the patch
    body for ``apply_patch``, the shell source for ``Bash`` — so one caller covers both.
    """
    event = {
        "hook_event_name": "PreToolUse",
        "session_id": "installed-codex-smoke",
        "turn_id": "turn-1",
        "model": model,
        "tool_name": tool,
        "tool_input": {"command": command},
        "cwd": project,
    }
    return subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(event),
        capture_output=True,
        check=False,
        env={"PATH": os.environ.get("PATH", ""), "PLUGIN_ROOT": str(hook.parents[1])},
        text=True,
    )


def _refusal_errors(result: subprocess.CompletedProcess[str], tool: str) -> list[str]:
    """What is wrong with the deny object, or nothing when Codex would act on it."""
    if result.returncode != 0:
        return [f"installed orchestrate hook exited {result.returncode} on {tool}: {result.stderr.strip()}"]
    try:
        output = json.loads(result.stdout)["hookSpecificOutput"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        return [f"installed orchestrate hook emitted no usable {tool} decision: {error}"]
    errors = []
    if output.get("hookEventName") != "PreToolUse":
        errors.append(f"the {tool} decision does not name the PreToolUse event")
    if output.get("permissionDecision") != "deny":
        errors.append(f"a project edit through {tool} on {ORCHESTRATOR_MODEL} was not denied")
    reason = output.get("permissionDecisionReason", "")
    if EDITED_PATH not in reason:
        errors.append(f"the {tool} refusal does not name the path it refused")
    if CLAUDE_AGENT in reason:
        errors.append(f"the Codex {tool} refusal incorrectly names Claude Code's {CLAUDE_AGENT} agent")
    return errors


def verify(install_root: Path) -> list[str]:
    """Return installed-artifact errors, or an empty list when the Codex hook is sound."""
    hook, errors = installed_hook(install_root)
    if hook is None:
        return errors
    manifest_path = hook.parents[1] / CODEX_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return [f"cannot read installed Codex plugin manifest {manifest_path}: {error}"]
    if manifest.get("hooks") != HOOK_CONFIG:
        return [f"{manifest_path} must declare hooks as {HOOK_CONFIG!r}"]

    with tempfile.TemporaryDirectory() as project:
        patched = _run(hook, ORCHESTRATOR_MODEL, project, "apply_patch", PATCH_BODY)
        shelled = _run(hook, ORCHESTRATOR_MODEL, project, "Bash", SHELL_EDIT)
        cheap = _run(hook, CHEAP_MODEL, project, "apply_patch", PATCH_BODY)
    errors = _refusal_errors(patched, "apply_patch") + _refusal_errors(shelled, "Bash")
    if cheap.returncode != 0 or cheap.stdout.strip():
        errors.append(f"a project edit on {CHEAP_MODEL} was not left alone: {cheap.stdout.strip()}")
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
    print(f"Codex orchestrate hook verified: {args.install_root.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
