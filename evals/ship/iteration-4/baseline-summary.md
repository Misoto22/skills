# Ship — iteration 4 rollout

## What this iteration is

An audit finding, not a failing case. `ship`'s description spent 129 characters
on its preflight:

> Runs a preflight first that marks each step RUN or SKIP, so a clean tree on
> the base branch exits without doing anything.

That is body identity. `SKILL.md` opens on it ("Step 0 inspects the repo and
prints an execution plan that marks each downstream step as `RUN` or `SKIP`"),
the step-classification table restates it per step, and the early-exit rule has
its own block quote. None of it is a trigger: no prompt routes to `ship` because
a preflight exists, so every turn paid for a sentence that could not fire.

`ship this` was also `ship it` written twice — one branch, two entries.

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
| `ship-it` | tuning | "Ship it." — `ship it` stays; only the duplicate `ship this` goes. |
| `get-merged` | tuning | "Get this merged once CI is green." — "wait for CI, merge" stays in the opening clause, and "get this merged" stays in the trigger list. |
| `chinese-merge` | tuning | `开个 PR 合了` — kept verbatim. |
| `chinese-push-and-merge` | holdout | `把这些改动推上去合并` — held by `把这些改动提上去` and `推上去合并`, both kept. Dropping either would aim at this case; neither is dropped. |
| `commit-message-only` | holdout | "Write me a commit message for this diff. Do not push anything." Held by the `Not for` clause, which is untouched. |
| `tag-release`, `just-pull`, `send-a-message-not-a-branch`, `too-blunt-to-send` | tuning | The four boundaries. `发出去` stays, so the `email` hand-off is still the contested one it was; the preflight sentence was never what settled it. |
