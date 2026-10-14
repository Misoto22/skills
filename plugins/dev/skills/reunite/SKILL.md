---
name: reunite
description: Make every signed-in account in the desktop app hold the same conversations, byte for byte. The app keeps one sidebar index per account and writes a rename, star, archive or deletion only into the signed-in account's copy, so the lists drift apart; this aligns every account onto the copy touched last, carries archives and deletions to all of them, and records every change for --undo. Use when asked why sessions disappeared after switching accounts, where my old conversations went, share sessions between two accounts, merge the session lists, an archived or deleted session still shows under another account, 换账号以后 session 都不见了, 会话历史没了, 两个账号共享会话, 把 session 列表合起来, 找回以前的对话, 删掉的会话在另一个账号还在. Not for deleting conversations on request, renaming them (that is retitle), or moving history between machines.
license: MIT
metadata:
  version: "0.21.0" # x-release-please-version
argument-hint: "[--apply] [--into=all|current|<accountUuid>] [--from=current|<accountUuid>] [--sidebar-from=current|<accountUuid>] [--no-environments] [--undo] [--undo-sidebar] [--install-service|--uninstall-service|--service-status]"
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

Every change the app makes — a rename, a star, an archive, a model switch — writes only the signed-in account's copy. A union that only adds missing entries cannot fix that: the entry is already present in the other accounts, so a union skips it, and they keep showing the old name, the unarchived row, the conversation already deleted. Running reunite again is the fix — not renaming a second time under the other account.

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

- **Everything it changes can be put back.** Each file it creates is listed in `.session-merge-manifest.json`; the original of each file it overwrites or removes is gzipped into `.session-merge-backup/` first, keeping only the earliest so a later run cannot replace it with something this script wrote. `--undo` removes the created files, restores every original with its mtime, and forgets the baselines and the service's record of its last pass. It is cumulative: it reverses every run since the manifest was started, not only the last. Manifests from before whole files were mirrored — a bare path list, or per-field title records — are still read.
- **It never deletes on request.** The only removals are the copies of a conversation the user already deleted under one account. Tidying the sidebar is not one of them: when rows a run added are unwanted, offer `--undo`, which takes back exactly what earlier runs wrote, and otherwise point the user at deleting in the app, which the next run carries to every account.
- **It never touches a transcript.** Everything it writes is under the index root, the environments file beside it, and — only with `--sidebar-from` or the service, only with the app quit — the layout and star keys in Local Storage.
- **Every file is replaced atomically.** Each index file and the environments file is written to a temporary beside it and renamed into place, so the app reading it at that moment, or a crash, never sees half of one.
- **It is idempotent.** A second run with nothing new plans no writes. Run it again after every stretch of work under one account: new conversations, names and archives only land in that account's copy.

## Environments

The environment picker — named working directories offered when a session starts — is kept in `~/Library/Application Support/Claude/ccd-session-presets.json` as `{"byAccount": {"<accountUuid>": {"presets": [...], "builtIns": {}, "seededFromDraft": true}}}`, and the app edits only the signed-in account's entry. A preset is a name and a machine path; nothing in it belongs to an account. `CLAUDE_DESKTOP_APP_DIR` names the directory holding the file when it is not the parent of the index root.

Every run aligns it in the same pass, and the report adds `environments: N to add, M to update, K removed`; `--no-environments` leaves the file alone.

- **Every account gets the union, one copy per `id`.** The copy with the newest `lastUsedAt`, then `createdAt`, wins; the order is that of the account holding the most recently used one. An account's own `builtIns` and `seededFromDraft` are kept, and copied from that account only where absent.
- **A deletion is carried and never brought back.** `.session-merge-environments.json` records the ids each account held at the last write. An id an account held then and does not now was deleted there: it is removed from every account and remembered with the time it was seen, and no later run copies it back — unless a copy created after that time turns up, which is the user making it again.
- **An account emptied since the last write is frozen.** The app empties an account when it recovers from a corrupt file or resets one, so an account that held presets and now holds none is read neither as deleting all of them nor as a target to refill. The report names it. Deleting every environment under one account therefore does not reach the others; delete them in each.
- **The app's limits hold.** It refuses more than 200 presets or an entry over 512 KiB, and so does this.
- **Recoverable like the rest.** The file is replaced atomically with its mode kept; its original is gzipped into `.session-merge-backup/` before the first write and recorded in the manifest, and `--undo` restores it. If the app writes the file between the read and the write, nothing is written and the run says to rerun.

Starred environments are not in this file — see the sidebar layout below.

## The sidebar layout

The index is not the whole sidebar. Manual groups and their members, section order, collapsed sections and per-section display prefs live in the app's Local Storage — a LevelDB at `~/Library/Application Support/Claude/Local Storage/leveldb/`, key `dframe-store`, one entry per `<accountUuid>/<orgUuid>` scope — so a group made under one account is missing under every other.

```bash
python3 scripts/merge.py --sidebar-from=current                # report each scope's manual groups and what would change
python3 scripts/merge.py --sidebar-from=<accountUuid> --apply  # write
```

`--sidebar-from` names the account whose layout is right and copies its sections and group names to every other account with an index directory, under `<account>/<the org that account lands in>` — created when missing. A copied manual group keeps only the conversations that account's index holds once aligned, which is why it runs in the same pass after the alignment. Global prefs and cached row counts are left alone.

It also copies the account's **starred environments**. The picker's Starred list lives in a separate Local Storage key per account, `LSS-persisted.code-projects-order.<accountUuid>`, whose `value` lists `preset::<presetId>` in display order. The source's value is written byte for byte to every other account's key, and a receiving account's key is deleted where the source has none. Layout and stars go in one LevelDB batch; no other key is written.

**The app must be fully quit** — Cmd-Q, not a closed window. It holds the database open and writes the layout back from memory, so anything written while it runs is lost. The script refuses while a process named `Claude` runs or anything holds LevelDB's `LOCK`, so it cannot run from the app's own Code tab or terminal: hand the user the command for Terminal, or run it from a `claude` session started there. It refuses before writing anything, the index included.

Before writing it copies the whole LevelDB directory to `.session-merge-backup/local-storage-<UTC timestamp>/` and records it in the manifest, appends one batch, and reads every written key back — restoring the copy and exiting non-zero if what landed differs. `--undo`, again only with the app quit, restores the earliest copy and keeps the directory it replaced under `.session-merge-replaced/`. `--undo-sidebar` reverts only the latest sidebar write — same checks, same kept copy — and forgets just its record, leaving every index file, the baseline and the rest of the manifest as they are. The layout appears when the app next starts.

It reaches only this machine's Code-tab sidebar. Artifacts, projects, chats and anything else claude.ai keeps server-side per account cannot be synced from here — say so when asked.

## What can never be synced

Only what this machine keeps on disk can be aligned. These live on claude.ai's servers per account, and nothing local reaches them:

- **Cloud environments** — only `local` presets are machine paths; a cloud environment belongs to the account that made it.
- **Artifacts, projects and chats.**
- **Routines and scheduled tasks.** `scheduled-tasks.json` sits under each `<account>/<org>/` in the index tree, but it is the app's local view of server-side routines, so reunite never reads or writes it — copying it would claim tasks the other account's server does not run.

## The background service

`--install-service` keeps everything above in step without anyone rerunning it. It is opt-in, macOS only, and refuses until a manual `--apply` has recorded a baseline: the service keeps an alignment the user has seen, it never makes the first one.

```bash
python3 scripts/merge.py --install-service     # copy scripts, write the agent, load it; again to upgrade
python3 scripts/merge.py --service-status      # loaded or not, last run and its result
python3 scripts/merge.py --uninstall-service   # unload, remove the agent and the copied scripts
```

Install copies `scripts/` to `~/Library/Application Support/reunite-service/scripts/` — a plugin's cache path changes with every update, so the agent must not point into it — and writes `~/Library/LaunchAgents/local.skills.reunite.plist` running that copy's `merge.py --service-run`: on any change to the index root or the environments file (`WatchPaths`), at load, and every five minutes, at most once every 30 seconds. It puts the installing interpreter's directory first on the agent's `PATH`, because launchd's own finds the system Python, which is too old; after upgrading Python, install again. Output goes to `~/Library/Logs/reunite-service.log`, one line per pass, never a title or file content; it rolls over at 1 MiB.

Each pass:

1. Takes an exclusive lock in the index root; if a pass or a manual `--apply` holds it, exits quietly. A manual `--apply` refuses while a pass holds it.
2. Skips the index when no index file's name, size or mtime moved since the last pass — reading every file costs far more than noticing none changed. Otherwise aligns it as `--apply` does, never `--from`, and only the baseline can prove a deletion.
3. Aligns the environments.
4. Only while the app is fully quit — the same `pgrep` and `LOCK` checks as `--sidebar-from` — copies the sidebar layout and stars from the account whose layout changed since the last pass. It keeps a hash per account in `.session-merge-service.json`: the one account whose hash moved is the source; if several moved, the one the app last signed in to (`lastKnownAccountUuid`) wins, and if it is not among them nothing is copied. The first pass, and an account seen for the first time, only record a hash, so a fresh account's empty layout never overwrites the others. While the app runs, the hashes are left as they were and the change waits for the next pass with the app quit. To seed the layout once, run `--sidebar-from=current --apply` by hand.

**It never resurrects a deletion.** A pass deletes nothing the baseline does not prove the user deleted, and copies back nothing the baseline recorded as deleted — the opposite of the retired handoff watcher, which recreated deleted entries every 30 seconds. **It is idempotent:** its own writes fire `WatchPaths` again, and the pass that follows writes nothing.

Every write is recorded in the manifest like a manual run's. `--undo` and `--undo-sidebar` refuse while the agent is installed — it would realign straight after, and a pass could interleave with the restore — so `--uninstall-service` first, then undo.

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

Then the environments:

```
Environments <presets file>
  <N> presets after aligning; <N> deletions kept out
  account <uuid> held presets at the last run and holds none now — left as it is
environments: <N> to add, <N> to update, <N> removed
```

With `--sidebar-from`, the report continues:

```
Sidebar layout <leveldb dir>
  from <scope>  <N> sections, <N> manual groups
  <scope>  <N> manual groups | (no layout yet)  → <N> sections, <N> manual groups, <N> members not in its index dropped
  starred environments from <account>: <N>
  <account>  <N> starred | (none)  → <N> starred
```

After `--apply`, quote `Environments aligned: <N> presets in <N> account(s)` — or `ENVIRONMENTS NOT ALIGNED`, which wrote nothing — and `Sidebar layout written to <N> scope(s)` with `Starred environments copied to <N> account(s)` — or `SIDEBAR NOT WRITTEN`, a failure whose backup was already restored. A service pass logs one line, `index: … | environments: … | sidebar: …`.

After `--apply`, say how many were created, overwritten and removed, quote the `Aligned:` line — or the `NOT ALIGNED` one, which is a failure to report as such — say that `--undo` takes all of it back, and that the sidebar is unchanged until the app restarts. A run reported as done while the sidebar still looks the same reads as a failure.

## Platform

The paths above are macOS, and the service is launchd only. `CLAUDE_DESKTOP_SESSIONS_DIR` overrides the index root, `CLAUDE_DESKTOP_APP_DIR` the directory holding the environments file, and `CLAUDE_DESKTOP_LOCAL_STORAGE_DIR` the Local Storage database; the script exits with that hint rather than guessing when the index or the database is not there, and skips the environments when the app has written no file yet. The service carries whichever of these are set when it is installed.
