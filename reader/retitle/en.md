A conversation list gets hard to use not because the names are ugly but because they carry nothing you can sort on. Clients generate a session name from whatever you happened to say first, and a week later the sidebar is a column of sentences. `retitle` gives every conversation a name that says when it happened, what kind of work it was, and what it was about, and it covers both halves of the problem: a hook names each new session as it starts, and a batch pass renames what is already there.

## The scheme

```
MMDD｜类型｜主题
```

The date is the conversation's **creation** time rather than its last-updated time, so the sidebar's chronology does not scramble because you reopened something old. The type is one of nine; a conversation that fits none of them is not given a tenth. The subject is what the conversation was actually about, in four to twelve characters, naming the object rather than the activity.

The separator is the fullwidth vertical line `｜` (U+FF5C), not an ASCII pipe, which would break the Markdown table this skill previews its renames in.

| Type | Covers |
|---|---|
| 功能 | New capability, endpoint, or screen |
| 设计 | Shape decided before code — architecture, interface, layout |
| 修复 | Something behaved wrongly and was corrected |
| 优化 | Behaviour was already correct; speed, cost or clarity improved |
| 发布 | Commit, pull request, merge, tag, deploy |
| 探索 | Tried something to find out what happens; no committed outcome |
| 文档 | README, comments, guides, changelogs |
| 审计 | Checked something you already own against a standard |
| 研究 | Read the outside world to answer a question |

The last two both end in a report and build nothing, so the line between them is drawn on whose thing is being looked at: 审计 inspects a repository, deployment, page or configuration you already own, and 研究 goes outside to answer a question. "Audit the site's SEO" is 审计; "which SEO tools are worth using" is 研究.

That split was counted rather than felt. Across 181 conversations under the earlier eight types, 研究 held 50% of them — half a sidebar reading the same word, which is a field carrying no information. Separating out the audits moved 25 of them.

## Naming new sessions as they start

Renaming by hand does not keep up with how fast a client opens new sessions, so the scheme is applied where sessions begin: a `UserPromptSubmit` hook that the skill installs into `~/.claude/scripts/`.

It fires the full rule on the first prompt and a short re-check every fifth prompt after. A session's direction drifts, but the full rule is long enough that injecting it every turn costs more than the title is worth; the re-check renames only on a real change of subject, because a title that moves every few messages is harder to use than one that is slightly stale.

The hook resolves the date itself, from the transcript's first timestamp rather than the clock, so a session running past midnight keeps the day it opened on. Every failure path exits 0 silently: a hook that throws blocks your prompt.

## Renaming what is already there

```
/dev:retitle
```

It prints a two-column table first (original name, new name), acts only after you confirm, and backs up the store before writing to it. That order holds whatever flags were passed — several hundred titles rewritten in a store you cannot easily diff is not a place to skip the preview.

A conversation whose subject cannot be recovered keeps its name and is counted as skipped rather than guessed at.

For Codex the write goes through the app server's `thread/name/set` rather than straight into the SQLite catalogue, because that table is derived: a title written into it is overwritten by a regenerated one at the next reconcile.

## What it does not do

It only renames. It does not touch what a conversation contains, which project it belongs to, or whether it is pinned, archived or ordered, and it does not rename projects, folders, branches, worktrees or files. Conversations mirrored from the cloud are left alone, because a local rename there is overwritten at the next sync. And for a client it has not been shown to understand, the proposed table is the whole deliverable — it will not reach into a store by guessing at the schema.
