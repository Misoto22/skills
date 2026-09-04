# Rollout — ship, iteration 3

The baseline is iteration 2's post-edit measurement: two samples of
`EVALS_SPLIT=all`, `deepseek-default` through the gateway.

| | sample 1 | sample 2 |
| --- | --- | --- |
| tuning routing | 7 / 7 | 7 / 7 |
| holdout routing | 2 / 2 | 2 / 2 |
| holdout behavior | 1 / 1 | 1 / 1 |
| tuning behaviors, valid cases | 4 | 7 |
| of those, clean | 1 | 4 |

## What failed

The same three that have failed throughout, plus the void rate: sample 1 lost
five of nine tuning cases to an invalid judge result or an empty generation.

- `chinese-conversation-english-commit` expectation 2 — stable across every run,
  before and after every edit. A real defect, and not this iteration's target.
- `tests-declared-only-in-ci` and `bump-lands-in-the-same-commit` — both fail by
  answering that nothing can be executed without repository state. They are the
  two cases that read the detection tables this iteration moves, which makes them
  the ones to read, and also the two whose failures are least attributable.

## This iteration's two edits

1. `Reporting`'s closing paragraph deleted — a sixth statement of why a version
   that does not move reaches nobody. 0h says it, at the point where `--bump`
   decides it.
2. The four marker tables in 0e–0h moved to `references/detection.md`. 0e, 0f and
   0h now name what to record and point at their section; 0g stays inline,
   because it is two commands rather than a lookup table.

The third budgeted edit is not spent. `ship` carried eight duplications, split
across three iterations as 3 + 3 + 2; there is no ninth to make up the number.

## What passed that this edit could break

This is the riskiest of the three iterations, and the reason is mechanical: the
tables are now behind a pointer, so a run that does not follow it has no markers
at all.

- `tests-declared-only-in-ci` — the case that exists because a repository can
  declare its test command only in CI. That rule is now in the reference, under
  *Test command*. If the pointer is weaker than the table, this case says so.
- `test-command-found-but-unrunnable` — passes in most samples. The rule it tests
  (name the command and why it did not run, rather than reporting no command)
  moved with the table.
- `bumper-found-no-flag` and `bump-lands-in-the-same-commit` — 0h keeps the
  `--bump` rule and loses only the marker table. Both must still refuse to invent
  a version and still report a detected bumper under `Attention`.
- The holdout cases reach neither changed block. `secret-in-a-new-untracked-file`
  is in step 3b, which no iteration here has touched.
