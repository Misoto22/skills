# Sync — iteration 2 rollout

## What this iteration is

An audit finding, not a failing case. `sync`'s description carried three
sentences the body already owns, and one of them was written twice:

- **Negation.** "It never rebases a feature branch, never resolves a conflict,
  and never discards a local commit." Three prohibitions in one clause, in the
  field that is loaded on every turn. Steering by prohibition drags the
  forbidden behaviour into context rather than out of it.
- **The same branch twice.** "never resolves a conflict" and "Not for …
  resolving a merge conflict" are one boundary stated in two places, 40
  characters apart.
- **Duplication inside the first sentence.** "fast-forward the base branch, and
  report what diverged" is restated by the sentence after it.

The body is the single source of truth for all three: `SKILL.md` opens with
"This skill only fast-forwards. Where a branch has diverged it reports and stops
— choosing between rebase, merge, and reset is the user's call, and guessing it
destroys work."

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

**The tuning split is at ceiling before the edit.** That is the fact this
iteration has to be read against: no edit can raise a score that is already 27
of 27, so the gate in `evals/ITERATION.md` cannot accept one on a rise. What it
can still do is veto — and that is what it is used for here. See
[benchmark-summary.md](benchmark-summary.md).

## What passed that this edit could break

Written before the edit, per `evals/ITERATION.md`:

| Case | Split | The surface the edit could take away |
| --- | --- | --- |
| `chinese-align` | tuning | `更新一下代码，跟 main 对齐` — the description drops `更新到最新` and `更新一下代码` and keeps `跟 main 对齐`. If the phrase carrying this prompt is the one removed, the trigger goes. |
| `catch-up` | tuning | "Get me up to date with the remote." — "update from main" and "catch up with remote" collapse into "get up to date with the remote". |
| `pull-latest` | tuning | "Pull the latest changes." — held by "pull latest", which stays. |
| `resolve-conflict` | holdout | "Resolve this merge conflict for me." Removing "never resolves a conflict" leaves the boundary stated once, in the `Not for` clause. If one statement is not enough, this is the case that says so. |
| `chinese-pull-latest` | holdout | `同步一下，拉最新的` — both phrases stay in the description. |
| `ship-it`, `delete-merged`, `chinese-push-up` | tuning | The three `routes_to` boundaries. A shorter `sync` competes for less, so these should hold or improve; a shorter neighbour is the way they would break. |
