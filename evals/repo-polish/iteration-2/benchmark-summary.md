# Repo polish — iteration 2 gate

## The edit

After "In short" in §1: where the rendered page cannot be opened — branch not pushed, host cannot reach the forge — say the render check was not run and why; never report the README as checked on the strength of its source.

## Gate

| | Before | After |
| --- | --- | --- |
| tuning | 7/12 | 5/12 |
| holdout | 0/2 | 1/2 |

Rejected: tuning fell. Per case, after: render-check-unpushed 0/2, picture-without-asset 2/2, chinese-request-english-repository 0/2, conflicting-licence-declarations 1/2, forge-write-confirmation 1/2, explicit-multiple-repositories 1/2.

The fall is not evidence the sentence is harmful. Every new failure is a "Does not …" expectation marked failed by a judge whose own reason describes compliance. Until those expectations are reworded, this suite cannot gate an edit that touches what a handoff claims. Records are per case under `.eval-runs/iter1113-repo-polish-*` in the main checkout; `compare-eval-runs.py` was not run because it takes one record per phase, not per case.
