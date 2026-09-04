# Rollout — ship, iteration 2

The baseline is iteration 1's post-edit measurement: two samples of `EVALS_SPLIT=all`
on the tree this iteration starts from, `deepseek-default` through the gateway.

| | sample 1 | sample 2 |
| --- | --- | --- |
| tuning routing | 7 / 7 | 7 / 7 |
| holdout routing | 2 / 2 | 2 / 2 |
| holdout behavior | 1 / 1 | 1 / 1 |
| tuning behaviors, violations | 5, 1 void | 5, 1 void |

## What failed

Iteration 1 established that this suite's tuning behaviors do not resolve a
change of this size: seven of nine cases changed state between two runs of the
same tree. See [iteration-1/benchmark-summary.md](../iteration-1/benchmark-summary.md)
for the case-by-case table.

One failure is stable across all three runs so far and is a real defect:

> `chinese-conversation-english-commit` expectation 2: the response gives no
> commit subject, branch name or pull request body, in English or otherwise.

It is not this iteration's target — the fix is about what the skill produces when
it cannot execute, which is a different change from removing duplication — but
edit 1 touches the step that names the branch, so it is the case to watch.

## This iteration's three edits

1. Step 1's own type list and slug rules, replaced by a citation of
   `shared/git.md` § Branch names. The rule moves *into* that heading first, so
   nothing is lost: the selection order and both slug fallbacks that only step 1
   carried are now stated there.
2. Step 7's opening and 7a — the home-worktree rule cited rather than restated,
   and `cleanup` named as a skill rather than as `/dev:cleanup`.
3. `Flags` — seven entries that re-explained their steps, reduced to seven that
   name them.

## What passed that this edit could break

- `worktree-holding-this-session` — expectation 3 is that step 7 still reaches
  7c and brings the primary checkout's base up to date. It failed at the original
  baseline, and edit 2 shortens 7a from four paragraphs to two, which is the
  change most likely to move it in either direction. The case to read first.
- `chinese-conversation-english-commit` — expectation 2 wants the branch name in
  English. Step 1 no longer says how a branch is named; `shared/git.md` does, and
  its first section is what language a git artifact is written in. If the citation
  is weaker than the copy, this is where it shows.
- `unpushed-commits-on-the-base` — passes in every run so far, and step 1 is
  edited. It must keep branching off rather than reporting an empty run.
- The holdout cases reach none of the three changed blocks. No wording here was
  written with one in view.
