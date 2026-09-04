---
name: reunite
description: Make every signed-in account see every conversation in the desktop app's sidebar. The app keeps one conversation index per account, so signing in as a second account hides the first account's history — this unions the indexes, adding entries and never removing one. Use when asked why sessions disappeared after switching accounts, where my old conversations went, share sessions between two accounts, merge the session lists, 换账号以后 session 都不见了, 会话历史没了, 两个账号共享会话, 把 session 列表合起来, 找回以前的对话. Not for deleting conversations, renaming them (that is retitle), or moving history between machines.
license: MIT
metadata:
  version: "0.15.0"
argument-hint: "[--apply] [--into=all|current|<accountUuid>] [--undo]"
---

# Reunite

Union the desktop app's per-account conversation indexes, so whichever account is signed in sees the whole history.

## What is actually lost

Nothing. Establish that before offering to fix anything, because the fix is much smaller than the symptom suggests.

Two stores hold a conversation, and only one of them knows about accounts:

| Store | Path | Account-aware |
|---|---|---|
| Transcript — the conversation itself | `~/.claude/projects/<slugged-cwd>/<cliSessionId>.jsonl` | **No.** The JSONL carries `cwd`, `sessionId`, `version`, `gitBranch` and no account field at all. |
| Index — what the sidebar lists | `~/Library/Application Support/Claude/claude-code-sessions/<accountUuid>/<orgUuid>/local_*.json` | **Yes.** Identity is the directory path; nothing inside the file names an account. |

So switching accounts hides conversations from the sidebar and deletes none of them. `claude --resume` in a terminal reads the transcript store directly and has been listing all of them the whole time — say so, because it is the answer for anyone who only needs to reach one old conversation.

## Run it

```bash
python3 scripts/merge.py                  # report only — what would be copied, and how much disk
python3 scripts/merge.py --apply          # write
python3 scripts/merge.py --undo           # remove exactly what --apply wrote
```

Report first, always. The report names each account index, its conversation count, and the org subdirectory a copy would land in. Read it out before writing: `--apply` on three accounts moved 114MB here, and someone who has not seen the number has not agreed to it.

`--into` narrows what receives the union — `all` (default), `current` for just the signed-in account, or a specific `accountUuid`. Narrow it when one of the accounts is long dead and does not deserve a copy of everything.

## What the script refuses to do

- **It never deletes.** Every run only adds files, and records what it added in `.session-merge-manifest.json` beside the account directories. `--undo` removes exactly those paths and nothing else — not files the app wrote, not files a previous merge already reconciled.
- **It skips orphans.** An index entry whose `cliSessionId` has no transcript under `~/.claude/projects/` would appear in the sidebar and open to nothing, which is worse than not appearing. The report counts them; `--keep-orphans` copies them anyway.
- **It is idempotent.** A second run plans zero copies. Run it again after every stretch of work under one account, since new conversations only land in that account's index.

## The restart

**A merge does not show up until the desktop app restarts.** The app reads this index at startup and does not rescan the directory while running — verified by writing an entry with a current timestamp and watching it stay invisible to a running app.

So the last line of any report is the restart, and it is worth naming what the restart costs: running conversations are interrupted. Check what is live first — `list_sessions` on the session-management MCP shows which ones are still running — and let the user pick the moment.

## Reporting

```
Session index <root>
  account <uuid>  <N> conversations  lands in <orgUuid>  <- signed in
  ...

Plan: <N> entries to copy into <M> account index(es), +<size>
  skipped <N> whose transcript is gone
```

After `--apply`, say how many were copied, that `--undo` takes them back, and that the sidebar is unchanged until the app restarts. A merge reported as done while the sidebar still looks the same reads as a failure.

## Platform

The paths above are macOS. `CLAUDE_DESKTOP_SESSIONS_DIR` overrides the index root; the script exits with that hint rather than guessing when the directory is not there.
