---
name: handoff
description: Mirror a live conversation into the other agent's history as it happens, so Claude Code sessions show up in Codex and Codex threads show up in Claude Code. Hooks on both sides watch their own transcript and write each exchange into the other side's format. Use when asked to share sessions between Claude and Codex, see my Codex conversations in Claude, continue this in Codex without re-explaining, keep the two agents' history in sync, 让 Codex 看到 Claude 的会话, 两个 agent 的历史同步, 把这段对话搬到 Codex, 在 Codex 里接着聊. Not for one agent's own per-account sidebar, which reunite covers; not for naming conversations; not for carrying history to a different computer.
license: MIT
metadata:
  version: "0.16.1"
argument-hint: "[install|status|uninstall]"
---

# Handoff

Mirror a live conversation into the other agent's history, so closing one tool and opening the other finds the work already there.

## Why this is possible at all

Claude Code and Codex converged on the same two mechanisms, which is the whole reason a bridge is cheap:

- **The same hook schema.** `~/.codex/hooks.json` uses Claude Code's shape — `PostToolUse`, `Stop`, `matcher`, `hooks[].command`, even `$CLAUDE_TOOL_ARG_*`. One script registers on both sides.
- **The same storage idea.** Both append one JSON object per line as the conversation runs. Neither writes a conversation only at the end, so a hook can read what has accumulated and translate just that.

They disagree on every field name, and that is all `scripts/formats.py` does:

| Claude Code | Codex |
|---|---|
| no header; `cwd` on every line | `session_meta`, first line only |
| `type:user`, `message.content` | `response_item/message` role=user |
| `type:assistant`, `content[text]` | `response_item/message` role=assistant |
| `content[thinking]` | `response_item/reasoning` |
| `content[tool_use]` | `response_item/function_call` |
| `type:user`, `content[tool_result]` | `response_item/function_call_output` |
| `parentUuid` linked list | file order, `turn_id` per item |

## Two things the existing converters get wrong

Worth knowing before reading their source, because both mistakes look like success.

**A mirror must be its own conversation.** Appending into a history the other tool has open races that tool's own writer. The mirror keeps its own id and its own file; the original is never touched.

**Writing the transcript is not enough on the Claude side.** The desktop app lists conversations from its own index under `~/Library/Application Support/Claude/claude-code-sessions/<account>/<org>/local_*.json`, not from `~/.claude/projects/`. A converter that writes only the transcript produces a file nothing displays. `write_index_entry` writes both, into the account the app is actually signed in as — which is `lastKnownAccountUuid` in the app's `config.json`, not the account `~/.claude.json` names.

Writing into Codex needs no equivalent: its catalogue is a projection a scanner derives from the rollout files, so the rollout is the whole job. Registering in its SQLite by hand, as `cc2cx` does, writes a row the scanner then regenerates.

## Run it

```bash
python3 scripts/handoff.py install     # register the hooks on both sides
python3 scripts/handoff.py status      # what is paired, how far each has read
python3 scripts/handoff.py uninstall   # drop this skill's entries, keep the mirrors
```

`install` copies both modules to `~/.claude/handoff/` and points the hooks there. A plugin lives in a version-pinned cache directory, so a hook pointing straight at it stops resolving the moment the plugin updates — and the hook ends in `|| true`, which is what keeps a mirror from failing a turn and also what hides that breakage. **Re-run `install` after every plugin update**; that is what moves the runner to the new version.

It edits `~/.claude/settings.json` and `~/.codex/hooks.json`, touching only entries whose command is this skill's — matched on the command, not on a path, so uninstall also claims entries an older install left pointing into a plugin cache. Every other hook in those files is left as it was, and installing twice replaces rather than stacks. Codex trusts a hook by hash, so the first Codex session afterwards asks to approve it.

Say what `install` will edit before running it. These are the user's own hook configurations, and a hook appearing in them unannounced is indistinguishable from one they did not ask for.

## The hook contract

`mirror` writes nothing to stdout and always exits 0. A hook's stdout is read as feedback by the agent that ran it, and a non-zero exit can stop a turn. Mirroring is bookkeeping and has no business doing either, so every failure is swallowed and recorded in the state file instead — `status` is where a broken mirror surfaces.

Each side keeps a byte watermark, so a `PostToolUse` hook firing two hundred times translates each exchange once. `read_jsonl` stops at the last newline: the hook fires while the other tool is mid-write, and the final line is routinely half-written.

## What does not survive

Say this plainly when offering the skill, because "synced" implies more than this delivers.

A mirror is a **readable record of what happened, not a resumable replay.** Codex encrypts its reasoning under its own key and Claude signs its thinking blocks; neither signature is reconstructible from the other side's text. So Claude's thinking arrives as a reasoning summary, and Codex reasoning that carries only `encrypted_content` is dropped rather than forged into a block Claude cannot verify.

Once mirrored, the two conversations are separate. Continuing on one side does not reach back to the other.

## The one guess

Codex's hook payload does not name the rollout it is writing, so `mirror --from=codex` falls back to the most recently modified rollout declaring that working directory. Two Codex sessions in one directory can therefore pair to the wrong file. The pairing is keyed by the file actually read rather than by the directory, so a wrong guess produces one wrong mirror instead of corrupting a right one — but say it is a guess when reporting.

## Reporting

```
Handoff state <path>
  <N> conversation(s) mirrored
  Claude → Codex  <started>  <project>
      read <N> bytes of source
  last run <time>: <what it did, or the error it swallowed>
  hooks in settings.json: installed (claude)
  hooks in hooks.json: installed, but pointing at a plugin cache (codex)
```

Both hook lines matter. Installed on one side only is a one-way mirror, which looks like a working sync until the day it is needed in the other direction. And `pointing at a plugin cache` means an install predating this runner, or one that has not been re-run since a plugin update: that hook resolves until the cache directory goes, then silently stops.
