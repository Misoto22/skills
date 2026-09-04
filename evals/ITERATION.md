# The iteration loop

How a skill's wording is changed here, and what has to be true before the change
is kept. Four steps, one gate.

The shape is taken from [SkillOpt](https://microsoft.github.io/SkillOpt/), which
treats a skill document as the trainable state of a frozen model and reports
gains of +9.1 to +24.9 points across seven models and six benchmarks. Its claim
is not that reflection helps — it is that reflection helps *only when it is
gated*: candidate edits are "accepted only when held-out selection improves",
and the edit budget "functions as a textual learning rate, preventing useful
rules from being overwritten by broad rewrites." Both halves are adopted below.
What is not adopted is the machinery — no optimizer model proposes edits here,
and nothing runs unattended.

## 1. Rollout

Score the tuning split and record what happened, one row per expectation.

```bash
LITELLM_EVALS_API_KEY=... EVALS_SPLIT=tuning bash scripts/run-evals-local.sh <skill>
```

An iteration starts from a measurement, not from a reading of the skill. A rule
that looks wrong on the page and passes every case is not the iteration's
business.

## 2. Reflect — on both sides

Two lists, written before any edit:

- **What failed**, and which sentence of `SKILL.md` was supposed to prevent it.
- **What passed that this edit could break.** This is the half that gets
  skipped, and it is the half that costs. In `email` iteration-1 a wording
  change made to fix one behavior case pushed another into answering `blocked`
  where it should have answered `draft` — a regression produced by the repair,
  found only because someone re-ran the case it broke.

A skill's contracts interact. Narrowing a refusal to stop one over-answer
loosens the surrounding language by contrast; tightening an English trigger
phrase is how a Chinese one stops firing.

## 3. Edit — within budget

**At most three edits per iteration per skill.** One edit is a single add,
delete, or replace of one contiguous block. No whole-section rewrite while an
iteration is open.

The budget is not tidiness. An iteration grades between ten and twenty
expectations; past three simultaneous edits, a gate that moves cannot be
attributed to any one of them, and the cheapest response — revert all three —
throws away the edit that worked. The budget is also what keeps a rule that
survived four iterations from being deleted by a rewrite that never knew it was
load-bearing.

If three edits are not enough, the iteration is too wide. Split it.

## 4. Gate

Score the holdout split. Keep the edit only if:

- the **tuning** score rose, **and**
- the **holdout** score did not fall.

```bash
LITELLM_EVALS_API_KEY=... EVALS_SPLIT=holdout bash scripts/run-evals-local.sh <skill>
```

SkillOpt accepts an edit only on a *strict* held-out improvement, because its
held-out set is large enough to rank one candidate against another. One case per
section cannot rank anything. It can only veto — so it is used as a veto, and
the tuning score remains the thing being improved. Calling a tripwire a search
objective would be the overfit one level up.

## The split

Every case is in one of two splits. A case carrying `"holdout": true` belongs to
the gate; every other case belongs to tuning.

**No edit may be aimed at a held-out case.** Not "should not" — the gate means
nothing otherwise. A skill re-measured on the cases that produced its wording
scores that wording back, which is exactly how `email` iteration-1 reached 100%:
the wording was narrowed in response to `ambiguous-reply` and then re-scored on
`ambiguous-reply`. The number was real; it just did not measure generalisation,
and nothing in the repository could tell the difference at the time.

Reading a held-out case while diagnosing a failure is unavoidable and fine.
Writing a sentence that answers one is not. If an iteration genuinely needs to
fix a held-out case, promote it into tuning and write a new holdout case for
that surface first — in that order, in a separate commit, with the reason in
`rejected.md`.

**Choosing one.** The holdout is the case whose surface the tuning cases cover
least:

- the only prompt in a language the rest of the section does not use;
- the output shape no other case asks for;
- a refusal `SKILL.md` states and no other case reaches.

Never a `routes_to` boundary. Those are the stated targets of a description
edit, so holding one out points the gate at exactly what tuning aims for.

`scripts/run-evals.py --check` holds the floors: at least three tuning triggers,
two tuning non-triggers, and one held-out case in every populated section.
Marking a case as holdout does not satisfy a tuning floor — it removes the case
from tuning, so one has to be written to replace it.

## What an iteration directory holds

`evals/<skill>/iteration-<n>/`:

| File | What it records |
| --- | --- |
| `baseline-summary.md` | the rollout: what failed, and what passed that the edit could break |
| `rejected.md` | every edit tried and dropped, and why — `none` when there were none |
| `benchmark-summary.md` | the gate: tuning before and after, holdout before and after |

`--check` fails on an iteration directory missing `rejected.md` — so write it as
a stub saying `none` when the directory is created, not when the iteration ends.
Discovering the rule half way through costs the scored runs that were in flight.

## rejected.md

The one part of an iteration nobody writes down, and therefore the one that gets
re-proposed. A dropped edit leaves no trace in the skill: the next person sees
wording that looks unnecessarily narrow, widens it, and re-runs the same
regression a release later.

One entry per dropped edit:

```markdown
## <what the edit was>

- **Aimed at** — the case or failure it was meant to fix.
- **Dropped because** — the case it broke, or the split that did not move.
- **Do not re-propose as** — the wording that will look like an improvement next time.
```

Write `none` when nothing was rejected, and say what that means — an iteration
whose first edit passed the gate is a small iteration, not a well-designed one.
