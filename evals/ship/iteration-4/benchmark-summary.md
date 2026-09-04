# Ship — iteration 4 gate

## The edit

One replace, of one contiguous block: the `description` line in
`plugins/dev/skills/ship/SKILL.md`.

| | |
| --- | --- |
| before | 534 characters |
| after | 401 characters |
| removed | 133 |

Two things went:

- **The preflight sentence**, 129 characters of it: "Runs a preflight first that
  marks each step RUN or SKIP, so a clean tree on the base branch exits without
  doing anything." `SKILL.md` opens on it, the step-classification table restates
  it per step, and the early-exit rule has its own block quote. It is also not a
  branch: no prompt routes to `ship` because a preflight exists, so this sentence
  could never fire, and was paid for on every turn regardless.
- **`ship this`**, which was `ship it` written twice.

Every other trigger is untouched, in both languages.

## The gate

```
                       tuning        holdout
before the edit        42 / 42        12 / 12
after the edit         42 / 42        12 / 12
```

Scored with `scripts/run-evals.py --run` through the repository's own gateway
and its own router prompt, one call per case, on all six `dev` skills together
— they compete for each other's prompts, so scoring one of them alone would
grade half of each boundary. The BEFORE column was scored against a snapshot of
`HEAD` so the pre-edit descriptions were the ones in the catalogue; the AFTER
column against the working tree.

## What the gate can and cannot say here

`evals/ITERATION.md` keeps an edit when **the tuning score rose and the holdout
score did not fall**. The first half of that sentence has no verdict to give in
this iteration, and the reason is worth writing down rather than working around:

**The tuning split was already at ceiling before the edit.** 42 of 42. Nothing
can raise it. Read strictly, that rule says a description may never be shortened
once its suite is green — which would forbid the pruning that `AGENTS.md` and the
`writing-for-agents` standard both require of a field loaded on every turn.

So the rule is applied for what it can measure and no further. The routing suite
measures exactly one thing about a description: whether it still wins the prompts
it should and stays out of the ones it should not. It measured that on both sides
of the edit, on both splits, and nothing moved. The benefit it cannot see — the
tokens a pointer costs on every turn whether or not it fires — is not estimated
here either. It is counted, above, in characters.

**This iteration therefore does not claim a gated improvement.** It claims a
measured non-regression and a counted reduction. Those are different sentences
and the second one is not evidence for the first. A maintainer reading
`ITERATION.md` strictly would drop this edit; the case for keeping it is that the
loop has no verdict for an edit whose objective is context load, not that the
loop was satisfied.

## What was not measured

A description edit changes the whole routing catalogue, not just its own skill's
entry in it. `steward` and `reunite` landed on `main` while this iteration was
open, and both are scored here for that reason: `steward` in particular claims
the sweep across every repository, so its `routes_to` non-triggers name `sync`,
`cleanup`, `ship` and `retitle` by hand. One of them, `同步一下，拉一下最新的`, is
`sync`'s own held-out trigger written from the other side — the trimmed `sync`
still wins it.

What is still unscored is the rest of the catalogue: `email` and `tempering` over
`发出去`, `repo-polish` over a repository. Those boundaries are covered here only
from this side of them — by the `routes_to` non-triggers inside these six suites,
all of which passed before and after. `check-descriptions.py` holds the static
half over the whole catalogue: with 23 descriptions published, the longest run of
words any of these four now shares with another is four, against a ceiling of
seven, and `run-evals.py --check` finds no Chinese trigger phrase two of them
claim without a suite settling it.
