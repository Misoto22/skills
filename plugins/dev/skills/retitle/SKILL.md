---
name: retitle
description: Normalize agent conversation titles onto a dated `MMDD｜类型｜主题` scheme across Codex, Claude Code, and any client that exposes its session list — the date comes from creation time, the middle field from a closed set of eight types, and every rename is proposed as a two-column table before a single title is written. Use when asked to 规范对话名称, 整理会话标题, 统一对话命名, 批量重命名会话, 会话名太乱了, clean up my conversation titles, rename my chat sessions, or make my session names consistent. Not for renaming projects, folders, git branches, worktrees, or files; not for editing, archiving, pinning, or deleting the conversations themselves.
license: MIT
metadata:
  version: "0.10.0"
argument-hint: "[--client=codex|claude-code] [--tz=<zone>] [--apply]"
---

# Retitle

Give every agent conversation a name that says when it happened, what kind of work it was, and what it was about — in that order, so a sidebar sorts and scans.

This skill renames. It never touches what a conversation contains, which project it belongs to, or whether it is pinned, archived, or ordered.

## 1. The scheme

```
MMDD｜类型｜主题
```

The separator is the fullwidth vertical line `｜` (U+FF5C), not the ASCII pipe `|`. This is not cosmetic: an ASCII pipe inside a title breaks the very markdown table this skill proposes its renames in, and a title that renders as three broken cells is worse than the name it replaced. Copy the character; do not retype it.

No spaces around the separator. `0903｜优化｜批次文字显示`, never `0903 ｜ 优化 ｜ 批次文字显示`.

`类型` is a closed set of eight. A conversation that fits none of them is not given a ninth — it keeps its original name:

| 类型 | Covers |
|---|---|
| 功能 | New capability, new endpoint, new screen |
| 设计 | Shape decided before code — architecture, interface, layout |
| 修复 | Something behaved wrongly and was corrected |
| 优化 | Behaviour was already correct; speed, cost, or clarity improved |
| 发布 | Commit, PR, merge, tag, deploy, publish |
| 探索 | Tried something to find out what happens; no committed outcome |
| 文档 | README, comments, guides, changelogs |
| 研究 | Read sources and reported findings; nothing built |

`主题` is what the conversation was actually about, in roughly four to twelve characters. Three rules govern it:

- **Do not repeat the project name.** The sidebar already groups by project, so `0903｜修复｜dealer-portal 登录失败` wastes the third of the title that is visible.
- **Name the object, not the activity.** `批次文字显示` beats `处理了一些显示问题`.
- **When the subject cannot be told from the conversation, do not invent one.** Keep the original title, verbatim, and report it as skipped. A confidently wrong title is worse than a messy honest one, because it is the version the user will trust.

Worked pairs:

| Original | New |
|---|---|
| 优化批次文字显示 | `0903｜优化｜批次文字显示` |
| 整合快捷键提示页面 | `0902｜功能｜整合快捷键提示页` |
| 提交代码到 GitHub | `0813｜发布｜提交代码到GitHub` |
| Clarify Sales Order pricing rules | `0901｜研究｜销售订单定价规则` |
| 新功能讨论 | *kept — the subject cannot be recovered from the title alone* |

The fourth pair is the one worth reading twice. The title alone said "clarify pricing rules", which sounds like 文档; the conversation was reading the existing rules and reporting what they were, which is 研究. Classify from the conversation, not from its current name — the current name is the thing being replaced precisely because it is unreliable.

## 2. Which date, and in which timezone

The date is `MMDD` of the conversation's **creation** time, never its last-updated time. A conversation reopened three weeks later must not migrate to the front of the list; the date is what makes the sidebar chronological, and updating it destroys the only ordering the scheme provides.

Timezone shifts the date by a day at the boundaries, so it is a declared parameter, not an assumption. Resolve it in this order:

1. `--tz=<zone>` when given.
2. Otherwise the system zone: `date +%Z` / `TZ` — the zone the user was actually in when the conversation happened.

State the resolved zone in the report. A run that does not name its timezone cannot be checked, and the reader has no way to tell a correct `0903` from an off-by-one `0902`.

## 3. Where the titles live

| Client | Store | Writable |
|---|---|---|
| Codex | `~/.codex/sqlite/codex*.db`, table `local_thread_catalog`, column `display_title` | Yes — section 6 |
| Claude Code | the session title API the harness exposes (`set_session_title` where present) | One session at a time — the current one |
| Anything else | whatever list the client exposes | Propose only — section 5 |

With no `--client`, detect: the Codex database existing makes Codex a target; a session-title tool being available makes the current Claude Code session a target. Report which clients were found and which were skipped.

## 4. Read the threads

For Codex, one query gets everything the naming needs. It writes nothing:

```bash
db=$(find ~/.codex/sqlite -maxdepth 1 -name 'codex*.db' ! -name '*summaries*' -print 2>/dev/null | head -1)
sqlite3 -json "$db" "
  SELECT thread_id, display_title, cwd, git_branch, source_kind,
         strftime('%m%d', source_created_at, 'unixepoch', 'localtime') AS mmdd
  FROM local_thread_catalog
  WHERE host_id = 'local' AND missing_candidate = 0
  ORDER BY source_created_at DESC;"
```

The database is found with `find` rather than `ls`, because `ls` is aliased to a different lister on plenty of machines and the alias returns bare names where the command needs full paths — the failure is an empty `$db` and a query that reads nothing while exiting zero. The `! -name '*summaries*'` excludes the separate turn-summary database, which carries no titles.

Three parts of that query are load-bearing:

- **`host_id = 'local'`.** Rows under a `chatgpt:…` host are a local mirror of the cloud catalogue. The cloud is their source, so a title written to them locally is reverted at the next sync — and until it is, the sidebar disagrees with itself. Filter them out and report the count as out of scope rather than renaming something that will not stay renamed.
- **`missing_candidate = 0`.** These are rows whose underlying session the scanner could no longer find. Renaming a conversation that is on its way out of the catalogue is wasted work.
- **`'localtime'`.** Applies the system zone from section 2. For an explicit `--tz`, run the query with `TZ=<zone>` set in the environment instead of hardcoding a zone into the SQL.

`display_title` is not a stored name. Codex derives it from the conversation's first user message, which is why the titles are messy and why this skill exists. Do not treat it as evidence of the subject — it is the same unreliable field for every row.

When the title alone is too thin to classify, read the conversation. The rollout file is at `~/.codex/sessions/<YYYY>/<MM>/<DD>/rollout-*-<thread_id>.jsonl`; the first few `response_item` entries with `"role": "user"` carry the actual request. Read the opening of the file, not all of it — these run to megabytes, and the subject is established in the first exchange.

## 5. Propose before writing

Print exactly one table, with exactly this header:

```
| 原名称 | 新名称 |
```

One row per conversation that would change. Conversations that keep their name are not rows — they are a count under the table, with their reasons. A table padded with unchanged rows hides the changes inside it.

Then stop. Applying without showing this table is the one thing this skill must not do, whatever `--apply` was passed: 317 titles rewritten in a store the user cannot easily diff is not something a preview can be skipped for.

Below the table:

```
proposed   <N> renames across <M> conversations
kept       <N> — subject not recoverable (<count>), already conforming (<count>)
excluded   <N> cloud-hosted, <N> missing from the catalogue
deferred   <N> inside the 30-day window — a rename there does not persist
timezone   <zone>, dates from creation time
```

## 6. Apply — Codex

Only after the table is confirmed.

**Back up first.** `VACUUM INTO` writes a consistent copy even while the app holds the database open, which a `cp` of a WAL-mode database does not:

```bash
sqlite3 "$db" "VACUUM INTO '$HOME/.codex/sqlite/backup-retitle-$(date +%Y%m%d-%H%M%S).db';"
```

Name the backup path in the report. A backup nobody can find is not a backup.

**Then write, one row at a time, parameterized by thread_id:**

```bash
sqlite3 "$db" "UPDATE local_thread_catalog SET display_title = ? WHERE host_id = 'local' AND thread_id = ?;" "$new_title" "$thread_id"
```

Four columns must not appear in that statement, and each for its own reason:

- **`source_updated_at`** — it decides whether the rename survives at all; see the window rule below. Writing it can only move a thread *into* the re-derived set, never out of it.
- **`observation_sequence`** — the scanner's own counter. Writing it corrupts its notion of what it has already seen.
- **`project_id`, `cwd`** — the grouping the titles are written to complement. The tweak that started this skill was explicit that project names stay untouched; so does the project a conversation sits in.
- **`pending_observed_title`** — a flag the app owns, marking a title it intends to replace. Setting it schedules the deletion of the rename that was just made.

### The 30-day window — read this before writing anything

Codex re-derives `display_title` from the conversation's first user message for **every
thread whose `source_updated_at` falls inside a rolling window of roughly 30 days**. A
rename written to such a thread is reverted the next time the app reconciles, which can
happen minutes later. The row's `observation_sequence` jumping to a fresh value is the
fingerprint of that revert.

Measured on one machine on 2026-09-04: of 156 renames, the 64 threads last updated more
than 30.95 days earlier all held; the 92 last updated less than 30.28 days earlier were
all reverted. No thread fell between those bounds, so the boundary is a clean 30 days,
not a heuristic.

There is no override. The local store has no user-authored-title column: this skill
checked `local_thread_catalog_metadata` (a revision counter), `thread_timeline_ledger`
(session start/end records only) and the separate turn-summaries database
(`compact_summary`, empty) and none of them holds a title the scanner defers to.

So **partition before writing**:

```bash
sqlite3 -json "$db" "
  SELECT thread_id, display_title,
         (strftime('%s','now') - source_updated_at) / 86400.0 AS age_days
  FROM local_thread_catalog
  WHERE host_id = 'local' AND missing_candidate = 0
  ORDER BY age_days;"
```

Write only the threads with `age_days > 31`. Report every thread inside the window as
`will not persist` and do not write it — a rename that reverts an hour later is worse
than none, because the user has no way to tell which titles are real. Say plainly that
those threads become renameable once they age out.

If the user wants a recent conversation renamed anyway, the only durable lever is the
first user message the title is derived from, which lives in the rollout file. This
skill does not edit it: rewriting what someone said to change a label is out of scope,
and section 7's proposal table is the honest deliverable instead.

If the client is running, the write lands but the sidebar may show the old title until it re-reads. Say so in the report rather than writing a second time; a second write does not make the first take effect sooner.

**Verify by reading back, not by trusting the exit code:**

```bash
sqlite3 "$db" "SELECT COUNT(*) FROM local_thread_catalog WHERE host_id='local' AND display_title LIKE '____｜%｜%';"
```

A count below the number proposed means rows did not take. Report the difference and name the threads, rather than reporting the number that was attempted.

## 7. Apply — Claude Code

Claude Code exposes the title of the **current** session only, so there is no batch here. Compose the name by the same rules and set it once through the tool the harness provides.

Renaming one session by hand is not the point, though. A client that keeps opening new sessions re-generates its own titles faster than anyone renames them, so the scheme has to be enforced where sessions are born. That is what `assets/session-naming-hook.py` is for, and installing it is part of applying this skill — not an optional extra.

### Install the hook

It is a `UserPromptSubmit` hook. Copy it next to the user's other Claude Code scripts and register it:

```bash
mkdir -p "$HOME/.claude/scripts"
cp assets/session-naming-hook.py "$HOME/.claude/scripts/session-naming-hook.py"
chmod +x "$HOME/.claude/scripts/session-naming-hook.py"
```

`$HOME/.claude` is the default configuration directory. Where the user has moved it, substitute the real one — the hook reads the same override itself when deciding where to keep its markers, so the two stay together.

Then add it to `settings.json` in that directory, under `hooks.UserPromptSubmit`, as a `command` entry running that path. Read the existing file and merge — a settings file rewritten from scratch loses whatever else the user had configured, which is the one failure here that costs more than a bad title.

Verify it before trusting it, because a hook that throws is a hook that breaks every prompt:

```bash
printf '{"session_id":"verify-install"}' | python3 "$HOME/.claude/scripts/session-naming-hook.py"
```

That must print one JSON object containing `MMDD｜类型｜主题`. Remove the marker it just created (`.session-naming-markers/verify-install` under the config directory) so a real session is not counted as already reminded.

### What the hook does, and why it is shaped that way

- **The full rule fires on a session's first prompt; a short re-check fires every fifth prompt after.** A session's direction drifts, and a title set in its first minute goes stale — but the full rule is long, and injecting it every turn would cost more context than the title is worth. `SESSION_TITLE_RECHECK_EVERY` in the environment changes the cadence; `0` fires once and never re-checks.
- **The re-check tells the model to retitle only on a real change of subject.** Without that bar a title changes every few messages, which is worse than one that is slightly stale, and the user watches it thrash.
- **It resolves `MMDD` itself** rather than asking the model, so a session running past midnight keeps the date it opened on.
- **Every failure path exits 0 with no output.** Unreadable event, unwritable marker, missing directory: the hook stays silent. A broken hook blocks the user's prompt, and no titling scheme is worth that.
- **It is Python with no imports beyond the standard library.** The obvious shell version needs `jq` to read the event, and a hook lands on whatever machine the skill was installed on.

The client auto-titles a new session before the model has done anything, so the first title a user sees is the client's, replaced moments later by the scheme's. That is expected, not a failure.

## 8. Everything else

For any other client, the table from section 5 is the deliverable. Do not reach into a store this skill has not been shown to understand: a schema guessed at is a schema that silently drops the wrong column.

## Reporting

```
Retitled <client>.
  scheme     MMDD｜类型｜主题, timezone <zone>
  renamed    <N> of <M> proposed
  kept       <N> — <reasons>
  excluded   <N> — <cloud-hosted | missing>
  deferred   <N> — inside the 30-day window, renameable once they age out
  backup     <path, or none for a client without one>
  attention  <threads that did not take, or none>
```

Every number comes from a read-back, not from the count of statements issued. `attention` names each thread that was proposed and did not land — silently dropping one is how a rename that half-happened gets reported as done.
