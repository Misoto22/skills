Every agent client names a conversation after whatever you happened to say first. A week later the sidebar is a list of sentences — no dates, no shape, nothing to scan. `retitle` replaces that with one structure, applied to both halves of the problem: a hook names each new session as it starts, and a batch pass renames everything already there.

## The scheme

```
MMDD｜类型｜主题
```

Three fields, in the order that makes a sidebar useful. `MMDD` is the day the conversation was **created**, so the list stays chronological — a session reopened three weeks later does not jump to the front. `类型` is one of nine kinds of work. `主题` is what it was about, in four to twelve characters, naming the object rather than the activity.

The separator is the fullwidth vertical line `｜` (U+FF5C), not an ASCII pipe. That is not cosmetic: an ASCII pipe breaks the Markdown table this skill previews its renames in.

| 类型 | Covers |
|---|---|
| 功能 | New capability, endpoint, or screen |
| 设计 | Shape decided before code — architecture, interface, layout |
| 修复 | Something behaved wrongly and was corrected |
| 优化 | Behaviour was already correct; speed, cost, or clarity improved |
| 发布 | Commit, PR, merge, tag, deploy |
| 探索 | Tried something to find out what happens; no committed outcome |
| 文档 | README, comments, guides, changelogs |
| 审计 | Checked something you already own against a standard |
| 研究 | Read the outside world to answer a question |

The last two are the pair worth reading twice. Both end in a report and build nothing, so the line is drawn on the **object**: 审计 inspects something you own, 研究 reads the outside world. "Audit the site's SEO" is 审计; "which SEO tools are worth using" is 研究.

## The live half

Renaming by hand loses. A client opens new sessions faster than anyone renames them, so the scheme has to be enforced where sessions are born — a `UserPromptSubmit` hook the skill installs into `~/.claude/scripts/` as part of applying it.

It fires the full rule on a session's first prompt and a short re-check every fifth prompt after, because a session's direction drifts but the full rule is too long to inject every turn. The re-check retitles only on a real change of subject: a title that moves every few messages is worse than one slightly stale.

Two decisions in it are worth knowing. It resolves the date itself, from the transcript's first timestamp rather than from the clock, so a session running past midnight keeps the day it opened on. And every failure path exits 0 with no output — a hook that throws blocks your prompt, and no titling scheme is worth that.

## The batch half

```
/dev:retitle
```

It reads what each client already holds, proposes every rename as a two-column table, and stops. Confirmation comes before any write, whatever flags were passed: several hundred titles rewritten in a store you cannot easily diff is not something a preview can be skipped for.

A conversation whose subject cannot be recovered keeps the name it had and is reported as skipped. A confidently wrong title is worse than a messy honest one, because it is the version you will trust.

For Codex the write goes through the app server's `thread/name/set`, not the SQLite catalogue — that table is a derived read-model, and a title written straight into it is reverted the next time the scanner reconciles the thread. The authoritative store is backed up before anything is written to it.

## What it will not do

It renames. It never edits what a conversation contains, which project it belongs to, or whether it is pinned, archived, or ordered. It does not rename projects, folders, branches, worktrees, or files. And for a client it has not been shown to understand, the proposed table is the whole deliverable — it will not reach into a store by guessing at the schema.
