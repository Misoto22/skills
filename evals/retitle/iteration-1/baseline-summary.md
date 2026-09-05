# Retitle — iteration 1 rollout

## What this iteration is

An audit finding, not a failing case. `retitle`'s description was the longest in
the repository at 671 characters, and 170 of them were one sentence of body
identity:

> The date comes from creation time, the middle field from a closed set of nine
> types, and every rename is proposed as a two-column table before a single
> title is written.

All three clauses are in the body, at more length and with the reasons attached:
the creation-time rule is in the report contract and in the SQL that reads
`source_created_at`; the nine types are a table with a paragraph on why AUDIT and
STUDY are separate; the preview rule has its own line — "Applying without showing
this table is the one thing this skill must not do, whatever `--apply` was
passed".

A pointer states what the material is and lists the branches that should trigger
reaching it. None of those three clauses does either job. The scheme itself,
`MMDD｜TYPE｜subject`, stays: that one is the material's name.

## Rollout

Routing, `EVALS_SPLIT=tuning`, all six `dev` skills scored together because they
compete for each other's prompts:

```
ship      tuning   7/7
cleanup   tuning   8/8
sync      tuning   6/6
retitle   tuning   6/6
steward   tuning   9/9
reunite   tuning   6/6
```

**The tuning split is at ceiling before the edit.** No edit can raise 42 of 42,
so the gate in `evals/ITERATION.md` cannot accept one on a rise; it is used as a
veto instead. See [benchmark-summary.md](benchmark-summary.md).

## What passed that this edit could break

| Case | Split | The surface the edit could take away |
| --- | --- | --- |
| `messy-titles` | tuning | "My conversation titles are a mess. Make them consistent." — "make my session names consistent" is kept. |
| `chinese-normalize` | tuning | `帮我规范一下对话名称，太乱了` — `规范对话名称` and `会话名太乱了` are kept. |
| `rename-sessions` | tuning | "Rename my Codex sessions so I can actually find things in the sidebar." — "Codex" and "rename my chat sessions" are kept. |
| `chinese-batch-rename` | holdout | `把 Codex 里所有会话标题统一改成带日期的格式`. Its surface is `整理会话标题`, `统一对话命名`, `批量重命名会话` and the word `dated`. **No trigger phrase is removed by this edit** — the whole cut is the one body-identity sentence — so nothing here is aimed at this case in either direction. |
| `chinese-rename-project` | holdout | `帮我把项目名称改一下` — held by the `Not for` clause, which is untouched and still names projects first. |
| `rename-branch`, `delete-old-chats`, `clean-merged-branches` | tuning | The three remaining boundaries, all held by the untouched `Not for` clause. |
