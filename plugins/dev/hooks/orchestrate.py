#!/usr/bin/env python3
"""UserPromptSubmit and PreToolUse hook: keep an orchestrator-class session out of the editor.

A session running on the most expensive model in the fleet spends that model on the
cheapest part of the work — typing the edit — unless something stops it. Prose asking a
model to delegate loses to the shorter path of just doing it, every time, on a long turn.
So the rule is enforced where the edit happens: on an orchestrator model the main thread
is reminded what its job is on every prompt, and its writes into the project are refused
with the dispatch it should have used instead. The directive repeats because the model
can change mid-session — a `/model` switch turns the rule on or off between two prompts
— and a repeated short paragraph needs no marker and no state file to get that right.
Subagents run on cheaper models and are untouched.

Both clients load the same `hooks/hooks.json`, so one script serves both. Claude Code
sends no model and marks a subagent with `agent_id`; Codex sends the active `model` on
every event and runs spawned agents on a different one, so the model alone answers there.
Codex also reports every file edit as `apply_patch`, with the patch body — not a path —
in `tool_input.command`, so the paths it writes are read out of the body's own headers.

Reads one event as JSON on stdin. On UserPromptSubmit it prints the delegation directive
on stdout and exits 0 — plain stdout on that event is added to the model's context in
both tools. On PreToolUse it prints the deny object on stdout and exits 0, which both
tools read as a refusal shown to the model. Everything else exits 0 silently, including
anything it cannot parse: a guard that blocks every tool call is worse than no guard.

The Bash half is a guardrail, not a sandbox. It recognises the common shell forms of a
file edit; a determined command still gets through, and that is the accepted trade. Its
job is to catch the orchestrator reaching for `sed -i` out of habit, not to contain it.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

SEGMENT = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")
REDIRECT = re.compile(r"\A(?:\d+|&)?>>?(.*)\Z", re.DOTALL)
MODEL_ARGUMENT = re.compile(r"--model[=\s]+(\S+)")
# `<<EOF`, `<<-'EOF'`, `<< "EOF"` — the word that closes the body the operator opens.
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
# Codex names every file an apply_patch body touches on a header line of its own.
PATCH_TARGET = re.compile(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$|^\*\*\* Move to: (.+)$", re.MULTILINE)
# The short flags sed and perl actually cluster with `i`. Reading any `-…i…` as in-place
# would turn `perl -Mstrict -e '…' file` and `-MList::Util` into refusals.
IN_PLACE_CLUSTER = re.compile(r"-[nrEszuplaw0]*i.*")

DEFAULT_ORCHESTRATOR_MODELS = "fable,gpt-6"
PLUGIN_OPTION = "CLAUDE_PLUGIN_OPTION_ORCHESTRATOR_MODELS"

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
PATCH_TOOL = "apply_patch"
ENV_COMMANDS = ("env", "/usr/bin/env", "/bin/env")
WRAPPER_COMMANDS = ("command", "exec")
ENV_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
MUTATING_VERBS = ("mv", "rm", "touch", "mkdir", "patch", "tee")
# `cp a b`, `ln -s a b`, `install -m 644 a b` read every operand but the last one.
DESTINATION_VERBS = ("cp", "ln", "install")
IN_PLACE_VERBS = ("sed", "perl")
# A redirect target that names a descriptor or the bit bucket writes no file.
HARMLESS_REDIRECTS = ("/dev/null",)

# Read only the tail: a long session's transcript reaches tens of megabytes, and the
# current model is always at the end of it.
TRANSCRIPT_TAIL_BYTES = 512 * 1024

DIRECTIVE = (
    "Orchestrator mode (dev plugin): this session runs on {model}, an orchestrator-class model. "
    "Your job here is to clarify the request, decompose it, dispatch work, and accept results. "
    "{delegation} "
    "Edits to project files from this thread are refused by the orchestrate hook; write briefs "
    "for subagents into the scratchpad instead. "
    "Set ORCHESTRATOR_MODELS to an empty string to switch this off."
)
CLAUDE_DELEGATION = (
    "Automatically delegate authorized code changes with the `Task` tool to `dev:implementer` "
    "(Opus), then use a separate `Task` call to `dev:verifier` (Sonnet) for independent checks. "
    "Older clients may expose the same dispatcher as `Agent`; use whichever name the current "
    "client provides. Use the built-in Explore agent for lookups."
)
CLAUDE_DISPATCH = (
    "Dispatch this change with the `Task` tool (`Agent` on clients that expose that legacy name) "
    "to `dev:implementer`, handing it the path, intent, and check that decides whether it worked."
)
BASH_ALLOWANCE = "Read-only commands, git, and running the project's checks are still allowed here."


def codex_role_models() -> tuple[str | None, str | None]:
    """Configured Codex implementation and verification models, without exposing other settings.

    Codex's collaboration tool inherits the parent model when ``model`` is omitted. The installed
    client already has one authoritative cheaper-model setting, ``agents.default_subagent_model``;
    ``review_model`` is the native optional verifier choice. Reading those two values here lets the
    directive name an explicit model without baking one provider's current catalogue into the
    plugin. A missing or malformed config produces no guess and the directive tells the model which
    setting it must resolve before dispatch.
    """
    home = os.environ.get("CODEX_HOME")
    root = Path(home).expanduser() if home else Path.home() / ".codex"
    try:
        config = tomllib.loads((root / "config.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return None, None
    agents = config.get("agents")
    agents = agents if isinstance(agents, dict) else {}
    implementation = agents.get("default_subagent_model")
    implementation = implementation.strip() if isinstance(implementation, str) else None
    implementation = implementation or None
    verification = config.get("review_model")
    verification = verification.strip() if isinstance(verification, str) else None
    verification = verification or implementation
    return implementation, verification


def delegation(kind: str) -> str:
    """Client-native automatic delegation instructions for the current installation."""
    if kind == "claude":
        return CLAUDE_DELEGATION
    implementation, verification = codex_role_models()
    if implementation:
        choices = (
            f'Pass `model: "{implementation}"` for implementation and '
            f'`model: "{verification}"` for verification.'
        )
    else:
        choices = (
            "Resolve `agents.default_subagent_model` from the current Codex configuration before "
            "dispatch and pass that value explicitly for both roles."
        )
    return (
        "Automatically delegate authorized code changes with `collaboration.spawn_agent`, using "
        '`fork_turns: "none"` and a complete task message. Wait for that child, then spawn a '
        "separate verification child that only runs the declared checks. "
        f"{choices} Omitting `model` inherits this orchestrator model, so never omit it."
    )


def dispatch(kind: str) -> str:
    """The concrete dispatch sentence used when an orchestrator attempts a project write."""
    if kind == "claude":
        return CLAUDE_DISPATCH
    implementation, _ = codex_role_models()
    model = f' with `model: "{implementation}"`' if implementation else " with an explicit model"
    return (
        f'Dispatch this change with `collaboration.spawn_agent`{model} and `fork_turns: "none"`, '
        "handing it the path, intent, and check that decides whether it worked."
    )


def orchestrator_models() -> list[str]:
    """Substrings of a model id that mark an orchestrator, lowercased.

    `ORCHESTRATOR_MODELS` is the hand-installed form, set on the hook's own command in
    settings.json. `CLAUDE_PLUGIN_OPTION_ORCHESTRATOR_MODELS` is how Claude Code hands a
    plugin hook the `orchestrator_models` option; Codex has no such option, so there only
    the bare variable or the default applies. The explicit variable wins, and an empty
    value is a deliberate off switch rather than a fall-through to the next source.
    """
    raw = os.environ.get("ORCHESTRATOR_MODELS")
    if raw is None:
        raw = os.environ.get(PLUGIN_OPTION)
    if raw is None:
        raw = DEFAULT_ORCHESTRATOR_MODELS
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def is_orchestrator(model: str | None) -> bool:
    """Whether a model id carries one of the configured orchestrator substrings."""
    if not isinstance(model, str) or not model:
        return False
    lowered = model.lower()
    return any(name in lowered for name in orchestrator_models())


def model_from_event(event: dict) -> str | None:
    """Codex names the active model on every event; Claude Code names none."""
    model = event.get("model")
    return model if isinstance(model, str) and model else None


def model_from_transcript(path: object) -> str | None:
    """The model of the last assistant line in a Claude Code transcript.

    This is the only source that survives a mid-session `/model` switch, so it outranks
    the launch argv below. It is written asynchronously and holds no assistant line at
    all on the first prompt of a session, which is why there is a third source.

    Only the last `TRANSCRIPT_TAIL_BYTES` are read, so a session whose whole final stretch
    is user records answers None rather than the model named before the window. That is
    the accepted trade: the argv below still answers, and reading tens of megabytes on
    every prompt to cover it would cost more than the case is worth.

    Splitting on `"\\n"` rather than `str.splitlines`: a JSON string may legally carry
    `\\r`, `\\x0b`, `\\x0c`, `\\x85`, U+2028 or U+2029, all of which `splitlines` treats as
    line breaks — that cuts the assistant record in half and loses the model on it.
    """
    if not isinstance(path, str) or not path:
        return None
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - TRANSCRIPT_TAIL_BYTES))
            tail = handle.read()
    except OSError:
        return None
    model = None
    for line in tail.decode("utf-8", "replace").split("\n"):
        found = _assistant_model(line)
        if found:
            model = found
    return model


def _assistant_model(line: str) -> str | None:
    """The model an assistant transcript line declares, or None for any other line.

    A subagent's turns land in the same transcript marked `isSidechain`, and they run on
    the cheaper model on purpose — reading one as the session's model would answer with
    exactly the model this hook exists to delegate to. The first line of a tail read is
    usually a fragment, so an unreadable line is skipped rather than fatal.
    """
    try:
        record = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("isSidechain"):
        return None
    if record.get("type") not in (None, "assistant"):
        return None
    message = record.get("message")
    model = message.get("model") if isinstance(message, dict) else record.get("model")
    return model if isinstance(model, str) and model else None


def _run_ps(pid: str) -> str | None:
    """The argv of a process, or None when it cannot be read. Patched in tests."""
    try:
        result = subprocess.run(
            ["ps", "-o", "command=", "-p", pid],
            capture_output=True,
            # The hook's own stdin is the event, already consumed; handing it to a child
            # would let a misbehaving `ps` read from it.
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=1,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def model_from_argv() -> str | None:
    """The `--model` the client process was launched with.

    The desktop app always passes it, and the CLI passes it when it was given. Stale
    after a `/model` switch, which is why the transcript is consulted first — but it is
    the only source that answers on the first prompt of a session.
    """
    pid = os.environ.get("CLAUDE_PID") or ""
    if not pid.isdigit():
        pid = str(os.getppid())
    argv = _run_ps(pid)
    if not argv:
        return None
    match = MODEL_ARGUMENT.search(argv)
    return match.group(1) if match else None


def resolve_model(event: dict) -> str | None:
    """The model this session runs on, from the first source that answers."""
    model = model_from_event(event)
    if model:
        return model
    model = model_from_transcript(event.get("transcript_path"))
    if model:
        return model
    return model_from_argv()


def client(event: dict) -> str:
    """Which client is running the hook, so the refusal names a tool that exists there.

    Claude Code marks its subprocesses with `CLAUDECODE`; Codex marks a plugin hook with
    `PLUGIN_ROOT` and sends `turn_id` where Claude Code sends `prompt_id`. Anything
    unrecognised counts as Claude Code, which keeps the hand-installed-hook behavior.
    """
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return "claude"
    if os.environ.get("PLUGIN_ROOT"):
        return "codex"
    return "codex" if "turn_id" in event and "prompt_id" not in event else "claude"


def inside_project(target: str, cwd: str) -> bool:
    """Whether a path lands under the project root, resolved without needing to exist.

    The orchestrator still writes briefs and memory — the scratchpad, `~/.claude`, `/tmp`
    — so only the project itself is refused. A relative path is resolved against the
    session's cwd, which puts it inside by construction.
    """
    if not target:
        return False
    try:
        base = os.path.realpath(cwd)
        full = os.path.realpath(os.path.join(base, os.path.expanduser(target)))
        return os.path.commonpath([base, full]) == base
    except (OSError, ValueError):
        return False


def _words(segment: str) -> list[str]:
    """The segment's tokens, or nothing when the quoting does not parse.

    guard-git falls back to a naive split here; this hook cannot, because a half-parsed
    command produces half-parsed paths and refusing on those would deny by accident.
    """
    try:
        return shlex.split(segment)
    except ValueError:
        return []


def _unwrap(words: list[str]) -> list[str]:
    """Remove shell wrappers that run, rather than merely describe, their command.

    `command sed`, `exec tee` and `env KEY=value sed` would otherwise hide the verb.
    Kept deliberately small, as in guard-git: treating an arbitrary word as a wrapper
    turns inspection commands into false refusals.
    """
    words = list(words)
    while words:
        if words[0] in WRAPPER_COMMANDS:
            words.pop(0)
            continue
        if words[0] not in ENV_COMMANDS:
            break
        words.pop(0)
        while words and ENV_ASSIGNMENT.fullmatch(words[0]):
            words.pop(0)
    return words


def _strip_heredocs(command: str) -> str:
    """The command with every heredoc body dropped, keeping the line that introduces it.

    A body is data, not shell source. `gh pr create --body "$(cat <<'EOF' … EOF)"` puts
    prose there, and a quoted line beginning `> ` would otherwise segment into a redirect
    to a file the author never named. The introducing line survives, because a redirect
    written beside the `<<` — `cat <<EOF > out.txt` — really does write that file.
    """
    lines = command.split("\n")
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        for terminator in [match.group(2) for match in HEREDOC.finditer(line)]:
            # `<<-` allows the terminator to be indented with tabs; plain `<<` does not,
            # and accepting it there only ever drops more data.
            while index < len(lines) and lines[index].lstrip("\t") != terminator:
                index += 1
            index += 1
    return "\n".join(kept)


def _redirect_targets(words: list[str]) -> list[str]:
    """Files a segment's `>` or `>>` would write, glued (`>file`) or standalone (`> file`).

    A descriptor duplication (`2>&1`) and `/dev/null` write no file, so neither counts.
    """
    targets = []
    for index, word in enumerate(words):
        match = REDIRECT.match(word)
        if not match:
            continue
        if match.group(1):
            target = match.group(1)
        elif index + 1 < len(words):
            target = words[index + 1]
        else:
            # A trailing `>` names nothing — a half-typed command, or a stray token left
            # by prose. Guessing a target for it would refuse at random.
            continue
        if not target.startswith("&") and target not in HARMLESS_REDIRECTS:
            targets.append(target)
    return targets


def _operands(words: list[str]) -> list[str]:
    """Words that name something rather than flag it.

    The empty string is dropped because BSD `sed -i '' 's/a/b/' file` passes one as the
    backup suffix; counting it as an operand shifts the file list by one.
    """
    return [word for word in words if word and not word.startswith("-")]


def _is_in_place(word: str) -> bool:
    """`-i`, `-i.bak`, `-pi` or `--in-place`, the flags that turn a filter into an editor."""
    if word == "--in-place" or word.startswith("--in-place="):
        return True
    if word.startswith("--"):
        return False
    return word.startswith("-i") or bool(IN_PLACE_CLUSTER.fullmatch(word))


def _verb_targets(words: list[str]) -> list[str]:
    """Files the segment's own command would write, by the verb it starts with."""
    if not words:
        return []
    verb = os.path.basename(words[0])
    rest = words[1:]
    if verb in MUTATING_VERBS:
        return _operands(rest)
    if verb in DESTINATION_VERBS:
        # Only the destination is written, and a lone operand names no destination at all.
        operands = _operands(rest)
        return operands[-1:] if len(operands) > 1 else []
    if verb in IN_PLACE_VERBS and any(_is_in_place(word) for word in rest):
        # The first operand is the script; the files it rewrites trail it.
        return _operands(rest)[1:]
    if verb == "git" and rest[:1] == ["apply"]:
        return _operands(rest[1:])
    return []


def bash_target(command: object, cwd: str) -> str | None:
    """The first project path a command would write, or None when it writes none.

    A guardrail, not a sandbox — see the module docstring. A command whose targets
    cannot be determined runs, because refusing what it cannot read would stop the
    orchestrator from running the checks it is supposed to be running.
    """
    if not isinstance(command, str):
        return None
    for segment in SEGMENT.split(_strip_heredocs(command)):
        words = _words(segment)
        if not words:
            continue
        for target in _redirect_targets(words) + _verb_targets(_unwrap(words)):
            if inside_project(target, cwd):
                return target
    return None


def patch_target(command: object, cwd: str) -> str | None:
    """The first project path an `apply_patch` body would write, or None when it writes none.

    Codex reports every file edit as `apply_patch` and puts the patch text — not a path —
    in `tool_input.command`, so the files are read out of the body's own headers. A rename
    writes both sides, and `*** Move to:` is the one that names the new file.
    """
    if not isinstance(command, str):
        return None
    for match in PATCH_TARGET.finditer(command):
        target = (match.group(1) or match.group(2)).strip()
        if inside_project(target, cwd):
            return target
    return None


def edit_target(tool_input: dict, cwd: str) -> str | None:
    """The project path an edit tool would write. NotebookEdit names its file differently."""
    path = tool_input.get("notebook_path") or tool_input.get("file_path")
    if not isinstance(path, str) or not path:
        return None
    return path if inside_project(path, cwd) else None


def deny(tool: str, path: str, kind: str, extra: str = "") -> dict:
    """The PreToolUse refusal both clients accept, with the dispatch it should have used."""
    reason = (
        f"Refused: {tool} on {path}. This session runs on an orchestrator-class model, and an "
        f"orchestrator does not edit project files itself. {dispatch(kind)} You remain the "
        "reviewer of what comes back: read the diff and the check output before accepting it."
    )
    if extra:
        reason = f"{reason} {extra}"
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _kind(event: dict) -> str | None:
    """Which of the two registered events this is, inferred when the client omits the name."""
    name = event.get("hook_event_name")
    if name in ("PreToolUse", "UserPromptSubmit"):
        return name
    if isinstance(event.get("tool_name"), str):
        return "PreToolUse"
    if any(key in event for key in ("prompt", "prompt_id", "turn_id")):
        return "UserPromptSubmit"
    return None


def on_prompt(event: dict) -> int:
    """Put the delegation directive in front of an orchestrator session, on every prompt.

    Repeating it is the point. A `/model` switch changes the answer between two prompts,
    so a directive printed once would either be missing after a switch into an
    orchestrator or stale after a switch out of one; printing it each time follows the
    model with no marker to write and no state file to keep in sync. It stays one short
    paragraph so that repetition costs context rather than attention.
    """
    model = resolve_model(event)
    if not is_orchestrator(model):
        return 0
    print(DIRECTIVE.format(model=model, delegation=delegation(client(event))))
    return 0


def on_tool(event: dict) -> int:
    """Refuse a write into the project, once the model is known to be an orchestrator.

    The target is resolved first: most tool calls are neither an edit nor a project
    write, and resolving the model costs a transcript read and possibly a `ps`.
    """
    tool = event.get("tool_name")
    tool_input = event.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    cwd = event.get("cwd")
    cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    if tool in EDIT_TOOLS:
        target, extra = edit_target(tool_input, cwd), ""
    elif tool == PATCH_TOOL:
        target, extra = patch_target(tool_input.get("command"), cwd), ""
    elif tool == "Bash":
        target, extra = bash_target(tool_input.get("command"), cwd), BASH_ALLOWANCE
    else:
        return 0
    if target is None or not is_orchestrator(resolve_model(event)):
        return 0
    print(json.dumps(deny(tool, target, client(event), extra)))
    return 0


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, OSError):
        return 0
    if not isinstance(event, dict) or not orchestrator_models():
        return 0
    # A subagent already runs on the cheap model this hook exists to route work to.
    if event.get("agent_id"):
        return 0
    kind = _kind(event)
    if kind == "UserPromptSubmit":
        return on_prompt(event)
    if kind == "PreToolUse":
        return on_tool(event)
    return 0


if __name__ == "__main__":
    sys.exit(main())
