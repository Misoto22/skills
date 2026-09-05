`handoff` makes a conversation you are having in one agent appear in the other one's history while it is still going. Work in Claude Code, close it, open Codex — the conversation is there. Work in Codex, open Claude Code — same.

## Why it is a small thing to build

The two tools converged, probably by borrowing from each other.

They fire hooks on the same events under the same configuration shape — Codex's `hooks.json` uses Claude Code's schema down to the environment variable names. And both write their history as one JSON object per line, appended as the conversation runs, rather than saved at the end. So a hook on either side can read what has accumulated since it last looked and write that into the other side's format.

What is left is a field-name translation: `type:assistant` here is `response_item/message` there, `content[tool_use]` is `function_call`, and so on. That table is the whole of the conversion.

## What it actually does

Every tool call and every completed turn, a hook reads the new lines of the conversation it is in and appends them, translated, to a mirror on the other side. The mirror is a separate conversation with its own id: appending into a history the other tool has open would race that tool's own writer, and a corrupted transcript costs more than a duplicated one.

```
python3 scripts/handoff.py install     # register the hooks on both sides
python3 scripts/handoff.py status      # what is paired, how far each has read
python3 scripts/handoff.py uninstall   # remove the hooks, keep the mirrors
```

`install` edits two files you may already have hooks in — `~/.claude/settings.json` and `~/.codex/hooks.json`. It touches only entries that name this script, and installing twice replaces rather than stacks. Codex trusts hooks by hash, so the next Codex session asks you to approve it once.

## What it is not

**It is a readable record, not a resumable replay.** Codex encrypts its reasoning under its own key and Claude signs its thinking blocks. Neither signature can be reconstructed from the other side's text, so the reasoning arrives as plain summary text where it survives at all. You can read the whole conversation on the other side and pick up from it; you cannot resume it as if it had been running there.

**The two copies diverge after the handoff.** Continuing in one tool does not reach back to the other.

**It does not slow anything down.** The hook writes nothing to stdout and always exits zero — a hook's output is read as feedback by the agent that ran it, and a failing hook can stop a turn. Mirroring is bookkeeping, so its failures are recorded in the state file and surface through `status` rather than in the middle of your work.

## The part that is a guess

Codex's hook payload does not say which file it is writing, so the Codex side falls back to the most recently modified rollout for that directory. Two Codex sessions in the same directory at the same time can pair to the wrong one. The pairing then sticks to the file it actually read, so a wrong guess makes one wrong mirror rather than corrupting a right one.
