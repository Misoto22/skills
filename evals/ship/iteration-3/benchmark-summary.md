# Gate — ship, iteration 3

Two edits of three budgeted. Both kept. The third was not spent; see
[rejected.md](rejected.md).

## Scores

`deepseek-default` through the evaluation gateway, `EVALS_SPLIT=all`, two samples
before and two after. A sample the judge or the generator could not complete is
void, not failing.

| | before, s1 | before, s2 | after, s1 | after, s2 |
| --- | --- | --- | --- | --- |
| tuning routing | 7 / 7 | 7 / 7 | 7 / 7 | 7 / 7 |
| holdout routing | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 |
| holdout behavior | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| tuning behaviors, valid cases | 4 | 7 | 7 | 9 |
| of those, clean | 1 | 4 | 4 | 4 |

**Holdout did not fall, in either sample. The edits are kept.**

## The pointer is followed

This iteration's risk was mechanical rather than stylistic: the marker tables are
behind a pointer now, so a run that does not open `references/detection.md` has
no markers at all. `tests-declared-only-in-ci` is the case that would show it —
its whole premise is a repository whose test command is declared only in CI.

Sample 2 answers it, and the judge's reason is the evidence:

> the candidate quotes the CI workflow command with `-v` dropped, but it does not
> actually execute that command

Quoting the CI command *with the CI-only decoration dropped* is the rule that
moved into `references/detection.md` § Test command. It is being applied from
there. The expectation still fails, for the reason it has failed since the
original baseline — the runner has no shell, so no suite can be run — but the
detection half of the case is reached through the pointer as reliably as it was
reached from the table.

`bumper-found-no-flag` passes in sample 2 and fails expectation 1 in sample 1,
which is where it has sat in every run of this suite. 0h keeps the `--bump` rule;
only its marker table moved.

## What is still unmeasured

`worktree-holding-this-session` was void in both of iteration 2's post-edit
samples, so edit 2 of that iteration remains unmeasured. It scores here — failing
in sample 1, passing in sample 2 — which is this suite's ordinary variance rather
than a reading of that edit.

## Across three iterations

Eight duplications removed from `ship`, split 3 + 3 + 2 so each gate could be
attributed. In practice none of the three tuning halves could be: across seven
scored runs, what moves between samples is whether the answer is a plan or a
refusal to act without repository state, and every expectation phrased as an
outcome turns on that. Routing was 9 / 9 in all seven. The held-out behavior case
passed in all seven.

That is what these three gates establish — **no regression on anything this suite
measures stably** — and it is deliberately less than a tuning improvement.
