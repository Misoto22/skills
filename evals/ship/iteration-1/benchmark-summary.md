# Gate — ship, iteration 1

Three edits of three budgeted. All kept, and the tuning half of the measurement
is reported as unusable rather than as a result.

## The edits

1. `## Common paths` deleted — four bullets re-rendering the step-classification
   table below them.
2. The early-exit blockquote and the paragraph under it deleted.
3. Step 0c rewritten to carry the early exit in one paragraph, beside the
   `git rev-list --count origin/<base>..<base>` whose answer decides it.

## Scores

`deepseek-default` through the evaluation gateway, `EVALS_SPLIT=all`. One
baseline sample and two after it. A sample the runner or the judge could not
complete is void, not failing.

| | baseline | after, sample 1 | after, sample 2 |
| --- | --- | --- | --- |
| tuning routing | 7 / 7 | 7 / 7 | 7 / 7 |
| holdout routing | 2 / 2 | 2 / 2 | 2 / 2 |
| holdout behavior | 1 / 1 | 1 / 1 | 1 / 1 |
| tuning behaviors, violations | 4 | 5, 1 void | 5, 1 void |

**Holdout did not fall, in either sample. The edits are kept.**

## The tuning half of this suite does not resolve a change this size

Seven of ship's nine tuning behavior cases changed state between two runs of the
*same* tree:

| Case | baseline | sample 1 | sample 2 |
| --- | --- | --- | --- |
| `tests-declared-only-in-ci` | fail | fail | **pass** |
| `worktree-holding-this-session` | fail | void | **pass** |
| `ci-has-not-registered-yet` | pass | pass | **fail** |
| `everything-was-classified-as-skip` | pass | pass | void |
| `bumper-found-no-flag` | fail | **pass** | fail |
| `bump-lands-in-the-same-commit` | pass | **fail** | pass |
| `chinese-conversation-english-commit` | fail | fail | fail |

Sample 1 was read as a regression in `bump-lands-in-the-same-commit` — three
expectations, from a clean pass. Sample 2 passes it and fails two other cases
instead. None of the three edits is anywhere near the version-bump path: 0h and
3a were not touched in this iteration.

What moves between samples is the *shape of the answer*, not the rule: a run
where the model answers "I cannot execute this without repository state" fails
every expectation phrased as an outcome, and a run where it answers with a plan
passes them. That is the class `evals/README.md` warns about, and it is a
property of the suite rather than of the wording under test.

So the only stable signals here are routing, the held-out behavior case, and
`chinese-conversation-english-commit`, which fails identically in all three runs
and is a genuine defect predating this iteration. All three held.

Reporting a tuning improvement off these numbers would be reporting noise. The
gate is recorded for what it can carry: **no regression on anything measurable.**
