# Rollout — ship, iteration 1

Scored 2026-09-05 with `bash scripts/run-evals-local.sh ship`, `EVALS_SPLIT=all`,
`deepseek-default` through the evaluation gateway. One sample.

| Split | Routing | Behaviors |
| --- | --- | --- |
| tuning | 7 / 7 | 5 of 9 cases clean, 4 expectation violations |
| holdout | 2 / 2 | 1 / 1 |

## What failed

Four violations, one per case, all in tuning:

| Case | Expectation | Reported |
| --- | --- | --- |
| `tests-declared-only-in-ci` | 1 | identifies the command but does not run the suite |
| `worktree-holding-this-session` | 3 | never brings the primary checkout's base up to date |
| `chinese-conversation-english-commit` | 2 | gives no commit subject, branch name or pull request body |
| `bumper-found-no-flag` | 1 | reports `Steps skipped: none` rather than marking 3a SKIP |

The first is unsatisfiable in this runner — there is no repository and no shell,
so no suite can be run. It is the class `evals/README.md` names, and it is left
alone: a case rewritten while an edit is open cannot tell a fix from an overfit.

The other three are skill defects, and two of them are what this iteration and
the two after it are about. `worktree-holding-this-session` stops at 7a and never
reaches 7c, which is what a 7a running to four paragraphs does to the step after
it. `bumper-found-no-flag` reports nothing skipped, which is the failure mode
`--bump` was explained five separate times to prevent.

## This iteration's three edits

The early exit was stated in four places: `Common paths`, a blockquote under the
classification table, the paragraph below that blockquote, and step 0c. Three of
those go; 0c keeps it, beside the command whose count decides it.

## What passed that this edit could break

- `unpushed-commits-on-the-base` — the case the early-exit wording exists for. It
  passes at baseline and must still pass: a clean tree on the base with three
  unpushed commits is shippable work, not an empty run. Both halves of the rule
  are now in one paragraph rather than split across a blockquote and a section
  seventy lines below it, which is meant to help this case, not only to shorten
  the file.
- `everything-was-classified-as-skip` — a *different* early exit, at step 4.
  Collapsing the step-0 statements must not read as collapsing this one too.
- `ship-it` and the routing cases — untouched; the description is not edited.

The holdout cases — `chinese-push-and-merge`, `commit-message-only`,
`secret-in-a-new-untracked-file` — reach none of the three changed blocks.
