---
name: reunite
description: Make every signed-in account in the desktop app hold the same conversations, byte for byte. The app keeps one sidebar index per account and writes a rename, star, archive or deletion only into the signed-in account's copy, so the lists drift apart; this aligns every account onto the copy touched last, carries archives and deletions to all of them, and records every change for --undo. Use when asked why sessions disappeared after switching accounts, where my old conversations went, share sessions between two accounts, merge the session lists, an archived or deleted session still shows under another account, 换账号以后 session 都不见了, 会话历史没了, 两个账号共享会话, 把 session 列表合起来, 找回以前的对话, 删掉的会话在另一个账号还在. Not for deleting conversations on request, renaming them (that is retitle), or moving history between machines.
license: MIT
metadata:
  version: "0.18.1" # x-release-please-version
argument-hint: "[--apply] [--into=all|current|<accountUuid>] [--from=current|<accountUuid>] [--undo]"
---

# Reunite

Align the desktop app's per-account conversation indexes, so every account lists the same conversations in the same state.

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
python3 scripts/merge.py                  # report only — what would change, and how much disk
python3 scripts/merge.py --apply          # write, then verify every account is identical
python3 scripts/merge.py --undo           # put back everything previous runs changed
```

Report first, always. The report names each account index, its conversation count, and the org subdirectory a new copy would land in, then counts what `--apply` would create, overwrite and remove — split into title, archive and star changes, because those are what the user sees. Read it out before writing: the first run on this machine created 891 copies and archived 2,702, and someone who has not seen those numbers has not agreed to them.

`--into` narrows which accounts are aligned — `all` (default), `current` for just the signed-in account, or a specific `accountUuid`. Narrow it when one of the accounts is long dead and does not deserve a copy of everything. Only `all` ends with every account identical.

`--from` is the reset for a tree that has drifted past reconciling: name the account whose sidebar is right — usually `current` — and every other account becomes a byte copy of it. Its archive flags win, and a conversation it does not hold is removed from every account. No baseline or mtime is consulted, and the authority's own files are never written. Use it when the user says "keep what this account shows, clean up the rest".

**Something else may be writing the index.** The retired handoff skill's watcher, where it is still installed, publishes an entry for every transcript into every account and recreates one that is missing, so a deletion made here comes back on its next pass. Check `launchctl list | grep handoff` before a cleanup, and say so if it is running.

**"Signed in" means the desktop app, not the CLI.** They hold separate logins and are routinely on different accounts, so `~/.claude.json` answers a different question — it names the account `claude` authenticates as, not the one whose sidebar is on screen. The app records its own as `lastKnownAccountUuid` in `config.json` beside the index, and that is the index a rename actually lands in. Check it before concluding a rename did not work; it may have worked in the other account.

## One conversation, one file, every account

Every change the app makes — a rename, a star, an archive, a model switch — writes only the signed-in account's copy. A union that only adds missing entries leaves the rest diverged, and the other accounts keep showing the old name, the unarchived row, the conversation already deleted.

So each run picks, per conversation, the copy written most recently: the one the user last touched. Its bytes become every account's copy, overwriting stale ones and creating missing ones, and every written file takes its mtime, so the copies are identical down to the timestamp and only a later change by the user can make one of them newest. After writing, the run rescans and checks that every conversation is byte-identical across the aligned accounts; it exits non-zero and names the ones that are not.

File mtime is the signal because it is the only timestamp every change moves — `lastActivityAt` records the conversation, not the record of it. It is not infallible: the app rewriting a stale copy for an unrelated reason makes that copy win. That is why the archive flag is not left to mtime.

## Archives and deletions

The archive flag decides whether the sidebar shows a conversation, so it is settled against a baseline rather than by mtime. Every `--apply` records `.session-merge-baseline.json`: which accounts held each conversation, and whether each copy was archived. The next run compares against it:

- **An archive flag that moved since the baseline is the user's change.** The newest one wins, archiving and unarchiving alike — even when another account's copy was touched more recently for some other reason.
- **An account that held a conversation and no longer does deleted it.** The conversation is removed from every account, and no later run copies it back. If it reappears where the baseline had none of it, the user resumed it, and it is aligned like any other.
- **An account directory that is gone altogether deletes nothing.** A signed-out account says nothing about one conversation.
- **With no baseline yet, disagreeing copies settle on archived.** Nothing recorded says which copy is newer, and hiding is the recoverable way to be wrong. A copy an earlier merge created, now missing from disk, still counts as a deletion: that is the only record from before the baseline existed.
- **A conversation whose transcript is gone is aligned, but archived.** It would open to nothing, so it is kept for the sake of an identical list and never shown. The transcripts are read from `$CLAUDE_CONFIG_DIR/projects` (default `~/.claude/projects`), and when none at all are found there nothing is treated as orphaned and the report says orphan detection was skipped.

A report-only run records nothing, so a deletion made between two reports is still seen by the next `--apply`.

## What makes it safe

- **Everything it changes can be put back.** Each file it creates is listed in `.session-merge-manifest.json`; the original of each file it overwrites or removes is gzipped into `.session-merge-backup/` first, keeping only the earliest so a later run cannot replace it with something this script wrote. `--undo` removes the created files, restores every original with its mtime, and forgets the baseline. It is cumulative: it reverses every run since the manifest was started, not only the last. Manifests from before whole files were mirrored — a bare path list, or per-field title records — are still read.
- **It never deletes on request.** The only removals are the copies of a conversation the user already deleted under one account. Tidying the sidebar is not one of them.
- **It never touches a transcript.** Everything it writes is under the index root.
- **It is idempotent.** A second run with nothing new plans no writes. Run it again after every stretch of work under one account: new conversations, names and archives only land in that account's copy.

## The restart

**A run does not show up until the desktop app restarts.** The app reads this index at startup and does not rescan the directory while running — verified by writing an entry with a current timestamp and watching it stay invisible to a running app.

So the last line of any report is the restart, and it is worth naming what the restart costs: running conversations are interrupted. Check what is live first — `list_sessions` on the session-management MCP shows which ones are still running — and let the user pick the moment.

## Reporting

```
Session index <root>
  account <uuid>  <N> conversations  lands in <orgUuid>  <- signed in
  ...

Plan: align <M> account index(es)
  <N> copies to create, +<size>
  <N> copies to overwrite with the canonical copy
    <N> change title
    <N> change isArchived
    <N> change isStarred
    <N> change other fields only the app reads
  <N> copies to remove — <N> conversations deleted under one account
  <N> conversations have no transcript left; they are kept, archived
    <account>  → <new title>
```

After `--apply`, say how many were created, overwritten and removed, quote the `Aligned:` line — or the `NOT ALIGNED` one, which is a failure to report as such — say that `--undo` takes all of it back, and that the sidebar is unchanged until the app restarts. A run reported as done while the sidebar still looks the same reads as a failure.

## Platform

The paths above are macOS. `CLAUDE_DESKTOP_SESSIONS_DIR` overrides the index root; the script exits with that hint rather than guessing when the directory is not there.
