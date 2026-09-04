# Gate — sync, iteration 1

Two edits of three budgeted. Both kept.

## The edits

Two table rows in `## 4` and `## 5` named `cleanup` by its Claude Code command
prefix, `/dev:cleanup`. They name the skill now. A prefix is the plugin's name
plus the skill's, so a skill that writes one down is wrong wherever a client
installs the skill directory on its own, and goes stale if the plugin is renamed.

## Scores

One sample each, `deepseek-default` through the evaluation gateway,
`EVALS_SPLIT=all`. A sample the runner could not complete is void, not failing.

| | baseline | after |
| --- | --- | --- |
| tuning routing | 6 / 6 | 6 / 6 |
| holdout routing | 2 / 2 | 2 / 2 |
| tuning behaviors, expectation violations | 2 | 2 |
| `all-skips-what-it-cannot-fast-forward` | pass | pass |
| `ahead-behind-not-transposed` | 2 violations | 2 violations |
| `dirty-tree-on-base` | pass | void — empty generation |
| holdout behavior | 1 / 1 | 1 / 1 |

**Holdout did not fall. Tuning did not move, and could not have.** Both edits are
aimed at no failing case: they rename a cross-reference and change no rule. There
was no score for them to raise, so the gate is used here as `ITERATION.md` says it
should be — a veto that did not fire — and this is deliberately not reported as a
tuning improvement.

The case named at risk in [baseline-summary.md](baseline-summary.md),
`all-skips-what-it-cannot-fast-forward`, still points the `[gone]` branch at
cleanup rather than deleting it. That was the thing worth checking: the rule
survives the rename because the skill's *name* is what carries it, not the prefix.

`ahead-behind-not-transposed` fails identically before and after, on expectations
that ask the runner for counts from a repository it cannot see.
