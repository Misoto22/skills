---
name: retitle
description: Normalize agent conversation titles onto a dated `MMDD｜TYPE｜subject` scheme — English by default, Chinese with `--lang=zh` — across Codex, Claude Code, and any client that exposes its session list. The date comes from creation time, the middle field from a closed set of nine types, and every rename is proposed as a two-column table before a single title is written. Use when asked to 规范对话名称, 整理会话标题, 统一对话命名, 批量重命名会话, 会话名太乱了, clean up my conversation titles, rename my chat sessions, or make my session names consistent. Not for renaming projects, folders, git branches, worktrees, or files; not for editing, archiving, pinning, or deleting the conversations themselves.
license: MIT
metadata:
  version: "0.14.0"
argument-hint: "[--client=codex|claude-code] [--lang=en|zh] [--tz=<zone>] [--apply]"
---

# Retitle

Give every agent conversation a name that says when it happened, what kind of work it was, and what it was about — in that order, so a sidebar sorts and scans.

This skill renames. It never touches what a conversation contains, which project it belongs to, or whether it is pinned, archived, or ordered.

## 1. The scheme

```
MMDD｜TYPE｜subject
```

The separator is the fullwidth vertical line `｜` (U+FF5C), not the ASCII pipe `|`. This is not cosmetic: an ASCII pipe inside a title breaks the very markdown table this skill proposes its renames in, and a title that renders as three broken cells is worse than the name it replaced. Copy the character; do not retype it.

No spaces around the separator. `0903｜TWEAK｜batch text rendering`, never `0903 ｜ TWEAK ｜ batch text rendering`.

`TYPE` is a closed set of nine, written uppercase. A conversation that fits none of them is not given a tenth — it keeps its original name:

| TYPE | Covers |
|---|---|
| BUILD | New capability, new endpoint, new screen |
| SHAPE | Shape decided before code — architecture, interface, layout |
| PATCH | Something behaved wrongly and was corrected |
| TWEAK | Behaviour was already correct; speed, cost, or clarity improved |
| SHIP | Commit, PR, merge, tag, deploy, publish |
| PROBE | Tried something to find out what happens; no committed outcome |
| WRITE | README, comments, guides, changelogs |
| AUDIT | Checked something that already exists against a standard and reported the gaps; nothing built |
| STUDY | Read sources and reported findings; nothing built and nothing of the user's inspected |

AUDIT and STUDY both end in a report and build nothing, which is why one collapses into the other unless the line is drawn on the **object**. AUDIT inspects something the user already owns — a repository, a deployment, a page, a configuration — against a standard. STUDY reads the outside world to answer a question. "Audit the site's SEO" is AUDIT; "which SEO tools are worth using" is STUDY.

The distinction earns its place empirically. Measured over 181 conversations before the audit type existed, the research type held 50% of them — half a sidebar reading the same word, which is a field carrying no information. Splitting the audits out moved 25 of those 90 and dropped the largest type to 36%.

### Why five uppercase letters

The type field has a job beyond meaning: hold a column, so the subject starts at the same place on every row and the eye reads down the list instead of hunting across it. Two CJK characters do this for free — every han glyph is one em, so 优化 and 研究 are the same width by construction, and the scheme got the property without anyone choosing it. English in a proportional UI font has no such property, and the natural words are its worst case: `FIX` against `DESIGN` is a factor of two, and at that spread there is no column left to read.

Fixing the letter count recovers most of it. At 13px in a system UI font these nine span about 3px across roughly 38px — under a tenth of a glyph — where the natural-word set spans 26px to 55px. Uppercase is the second half of the same decision: capitals have neither ascenders nor descenders and vary less in width than lowercase, and the field reads as a tag rather than as a word competing with the subject beside it.

`SHIP` is the one four-letter member, and it is chosen rather than settled for. No honest five-letter English verb covers commit, PR, merge, tag, deploy and publish at once; `MERGE` holds the column by describing one member of that set as though it were all of them. One character of raggedness on one of nine types costs less than a type that lies about what it covers.

### The subject

`subject` is what the conversation was actually about, in two to four lowercase words and at most 24 characters. English runs about two and a half times wider than Chinese for the same meaning — `批次文字显示` is six glyphs where `batch text rendering` is twenty — so in a narrow sidebar it is this field that gets truncated, not the type, and the cap is what keeps the type visible at all. Three rules govern it:

- **Do not repeat the project name.** The sidebar already groups by project, so `0903｜PATCH｜acme-portal login fails` wastes the third of the title that is visible.
- **Name the object, not the activity.** `batch text rendering` beats `fixed some display issues`.
- **When the subject cannot be told from the conversation, do not invent one.** Keep the original title, verbatim, and report it as skipped. A confidently wrong title is worse than a messy honest one, because it is the version the user will trust.

Worked pairs:

| Original | New |
|---|---|
| 优化批次文字显示 | `0903｜TWEAK｜batch text rendering` |
| 整合快捷键提示页面 | `0902｜BUILD｜unified shortcut page` |
| 提交代码到 GitHub | `0813｜SHIP｜push code to github` |
| Clarify Sales Order pricing rules | `0901｜STUDY｜sales order pricing` |
| 对网站的 SEO 进行审查 | `0904｜AUDIT｜site seo review` |
| 新功能讨论 | *kept — the subject cannot be recovered from the title alone* |

The fourth pair is the one worth reading twice. The title alone said "clarify pricing rules", which sounds like WRITE; the conversation was reading the existing rules and reporting what they were, which is STUDY. Classify from the conversation, not from its current name — the current name is the thing being replaced precisely because it is unreliable.

### Chinese, by request

`--lang=zh` swaps the vocabulary for the one this scheme started as:

```
MMDD｜类型｜主题
```

功能, 设计, 修复, 优化, 发布, 探索, 文档, 审计, 研究 — in that order against the table above — with 主题 at roughly four to twelve characters rather than a character cap. Nothing else moves: the separator, the creation-date rule, and the closed set of nine are the same. Chinese needs no width argument, because two han glyphs are two ems whatever they say.

**The choice reaches the whole run, not just the titles.** The preview table's header and the summary under it are written in the run's language too — section 5 gives both forms. A scheme whose point is that a sidebar should not be half one language and half another cannot hand back a report that is exactly that.

A run that does not pass `--lang` names in English.

**A title already conforming in either language is kept.** This is the rule that stops a default run from rewriting a sidebar someone has spent months naming in Chinese: `0903｜优化｜批次文字显示` conforms, so it is not a row in the proposal table and not a rename. Moving an existing store from one language to the other is a deliberate request, not something a default does on its way past — when it is asked for, every conforming title becomes a row like any other and the preview table shows all of them.

## 2. Which date, and in which timezone

The date is `MMDD` of the conversation's **creation** time, never its last-updated time. A conversation reopened three weeks later must not migrate to the front of the list; the date is what makes the sidebar chronological, and updating it destroys the only ordering the scheme provides.

Timezone shifts the date by a day at the boundaries, so it is a declared parameter, not an assumption. Resolve it in this order:

1. `--tz=<zone>` when given.
2. Otherwise the system zone: `date +%Z` / `TZ` — the zone the user was actually in when the conversation happened.

State the resolved zone in the report. A run that does not name its timezone cannot be checked, and the reader has no way to tell a correct `0903` from an off-by-one `0902`.

## 3. Where the titles live

| Client | Store | Writable |
|---|---|---|
| Codex | `~/.codex/session_index.jsonl`, written only through the app server's `thread/name/set` | Yes — section 6 |
| Codex | `~/.codex/sqlite/codex*.db`, `local_thread_catalog.display_title` | **No** — derived from the above; reading only, section 4 |
| Claude Code | the harness's session API (`list_sessions`, `get_session`, `set_session_title`) | Yes, any session by id — section 7 |
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
| OLD | NEW |
```

Under `--lang=zh` it is `| 原名称 | 新名称 |`, and so is everything else below. One run speaks one language: Chinese titles under English headings is the mixture this scheme exists to remove from a sidebar, and reproducing it in the skill's own output would be the same failure one screen further out.

One row per conversation that would change. Conversations that keep their name are not rows — they are a count under the table, with their reasons. A table padded with unchanged rows hides the changes inside it.

Then stop. Applying without showing this table is the one thing this skill must not do, whatever `--apply` was passed: 317 titles rewritten in a store the user cannot easily diff is not something a preview can be skipped for.

Below the table:

```
proposed   <N> renames across <M> conversations
kept       <N> — subject not recoverable (<count>), already conforming (<count>)
excluded   <N> cloud-hosted, <N> missing from the catalogue
timezone   <zone>, dates from creation time
language   en
```

Under `--lang=zh`:

```
提案   <N> 处改名，共 <M> 条对话
保留   <N> —— 主题无法还原（<count>）、已合规范（<count>）
排除   <N> 条云端来源、<N> 条已不在目录中
时区   <zone>，日期取创建时间
语言   zh
```

## 6. Apply — Codex

Only after the table is confirmed.

**Do not write `local_thread_catalog.display_title`.** That table is a derived read-model: Codex rebuilds `display_title` from the conversation's first user message, and a title written straight into it is reverted the next time the scanner reconciles that thread. Measured on one machine, 156 such writes held for exactly as long as the scanner ignored them — every thread it later observed went back to its old name, with `observation_sequence` bumped as the fingerprint.

The authoritative name lives in `~/.codex/session_index.jsonl`, an append-only log of `{id, thread_name, updated_at}`, and the only supported way to write it is the app server's JSON-RPC method `thread/name/set`. That is the same call the client's own rename command makes, which is why it lasts: the catalogue is then rebuilt *from* the name rather than over it.

### Speak to the app server

`codex app-server` speaks line-delimited JSON-RPC on stdin and stdout. Handshake first, then one request per rename:

```json
{"id":0,"method":"initialize","params":{"clientInfo":{"name":"retitle","version":"1.0"}}}
{"id":1,"method":"thread/name/set","params":{"threadId":"<thread_id>","name":"<MMDD｜TYPE｜subject>"}}
```

A successful rename answers `{"id":1,"result":{}}`. Read the replies rather than counting the requests sent — the server answers out of order, and it rejects under load (see below).

Confirm with `thread/read`, which returns the thread's `name` as the server now understands it. That is the readback this skill trusts; the database is downstream of it and lags.

Do not resume a thread first. `thread/resume` loads the whole conversation to no purpose here, and `thread/name/set` works without it.

### The server rejects under load

Sending every rename at once returns `-32001 Server overloaded; retry later` for the tail of the batch — on one run, 126 of 156 succeeded and 30 were refused. The refusal is clean: nothing partial is written, and the request can simply be repeated.

So send in batches of about 20 with a short pause between them, and drive the retry off the store rather than off the error list:

```bash
python3 -c "import json,os;
[print(json.loads(l)['id'], json.loads(l)['thread_name']) for l in open(os.path.expanduser('~/.codex/session_index.jsonl'))]"
```

Take the last record per `id`, compare against the plan, and resend only what does not match. A retry loop written that way is idempotent — it converges whether the failure was a rejection, a dropped reply, or a crash halfway through.

### Back up first

The store is one file, so the backup is one copy:

```bash
cp ~/.codex/session_index.jsonl ~/.codex/session_index.jsonl.bak-$(date +%Y%m%d-%H%M%S)
```

The log is append-only and keyed by last write, so restoring means putting that file back — no surgery on individual records.

## 7. Apply — Claude Code

Claude Code's session API addresses **any** session by id, so this half is a batch like Codex's:

| Call | Use |
|---|---|
| `list_sessions` | every session, `include_archived: true` — the archived ones are exactly the finished work whose titles nobody will fix later |
| `get_session` | one session's `createdAt`, which is the field section 2 requires. The listing carries only `lastActivityAt`, and naming a session for the day it was last touched puts it under the wrong date |
| `set_session_title` | the rename, by `sessionId` or the literal `"self"`. `session_id` is required — a call that omits it fails validation, and the id in a session's own transcript or scratchpad path is a different id that answers "not found" |

The client auto-titles a new session before the model has done anything, so `list_sessions` mixes generated titles with any the scheme has already set. Skip the ones that already conform, in either language, rather than re-deriving them — a session renamed twice is a session whose subject drifts for no reason, and a default English run must not sweep up sessions already named in Chinese.

Renaming one session by hand is not the point, though. A client that keeps opening new sessions re-generates its own titles faster than anyone renames them, so the scheme has to be enforced where sessions are born. That is what `assets/session-naming-hook.py` is for.

### The hook ships with the plugin

Installed as the `dev` plugin, the hook is already registered: the plugin's `hooks/hooks.json` runs it on every `UserPromptSubmit`, and disabling the plugin unregisters it. Nothing is copied and no settings file is edited. `claude plugin details dev@<marketplace>` lists it among the plugin's components.

The hook names in English unless the plugin's `session_title_lang` option says otherwise:

```bash
claude plugin install dev@<marketplace> --config session_title_lang=zh
```

`/plugin configure` sets the same option interactively. A locale tag works as well (`zh-CN`, `zh_Hans`), and an unrecognised value falls back to English rather than failing — a rule in the wrong language still names the session, and a hook that refuses to emit one does not.

A machine that installed the hook by hand before the plugin carried it now runs two copies. Remove the `UserPromptSubmit` entry from `settings.json` and the script from `~/.claude/scripts/`; the plugin's copy takes over on the next prompt.

Where the skill was copied on its own — `npx skills add`, skills.sh, or any client that installs a skill directory rather than a plugin — there is no plugin to register it. [references/hook-install.md](references/hook-install.md) installs it by hand.

### What the hook does, and why it is shaped that way

- **The full rule fires on a session's first prompt; a short re-check fires every fifth prompt after.** A session's direction drifts, and a title set in its first minute goes stale — but the full rule is long, and injecting it every turn would cost more context than the title is worth. `SESSION_TITLE_RECHECK_EVERY` in the environment changes the cadence; `0` fires once and never re-checks.
- **The re-check tells the model to retitle only on a real change of subject.** Without that bar a title changes every few messages, which is worse than one that is slightly stale, and the user watches it thrash.
- **It names `session_id: "self"` in the call it asks for.** Left to infer the argument, a model calls `set_session_title` with a title alone, is told `session_id` is required, then supplies the session id it can see — the one in its transcript or scratchpad path. That is the CLI's id, not the client's, so the second call answers "not found" and the session keeps the title the client generated. Two failed calls and a silently unrenamed session is what one missing sentence cost.
- **It resolves `MMDD` itself** rather than asking the model, so a session running past midnight keeps the date it opened on.
- **It carries one language's vocabulary, not both.** Injecting the nine types twice would double the longest part of the rule to let the model pick a language it has no basis for picking — the machine's owner has already decided, so the `session_title_lang` option decides once (`SESSION_TITLE_LANG` on a hand-installed command) and the rule that reaches the model names one set.
- **Every failure path exits 0 with no output.** Unreadable event, unwritable marker, missing directory: the hook stays silent. A broken hook blocks the user's prompt, and no titling scheme is worth that.
- **It stays silent under Codex.** Codex loads the same plugin hooks and runs the script on every prompt, but has no tool that renames the running thread, and a rule nothing can act on is context spent for nothing.
- **It is Python with no imports beyond the standard library.** The obvious shell version needs `jq` to read the event, and a hook lands on whatever machine the skill was installed on.

The client auto-titles a new session before the model has done anything, so the first title a user sees is the client's, replaced moments later by the scheme's. That is expected, not a failure.

## 8. Everything else

For any other client, the table from section 5 is the deliverable. Do not reach into a store this skill has not been shown to understand: a schema guessed at is a schema that silently drops the wrong column.

## Reporting

```
Retitled <client>.
  scheme     MMDD｜TYPE｜subject, timezone <zone>
  renamed    <N> of <M> proposed
  kept       <N> — <reasons>
  excluded   <N> — <cloud-hosted | missing>
  backup     <path, or none for a client without one>
  attention  <threads that did not take, or none>
```

Under `--lang=zh`:

```
已重命名 <client>。
  规范     MMDD｜类型｜主题，时区 <zone>
  已改名   <N> / 提案 <M>
  保留     <N> —— <原因>
  排除     <N> —— <云端来源 | 已不在目录中>
  备份     <路径，没有备份的客户端写 none>
  注意     <没有落地的会话，或 none>
```

Every number comes from a read-back, not from the count of statements issued. `attention` names each thread that was proposed and did not land — silently dropping one is how a rename that half-happened gets reported as done.
