# Rejected edits — iteration 2

Three candidates were written and dropped before the kept one. None reached a
score: two were dropped on a static reading of the suite, which is the cheaper
place to catch an edit that would remove a trigger a case lands on.

## Drop `拉一下最新的` as a duplicate of `更新到最新`

- **Aimed at** — the audit's "one trigger per branch": `同步一下`, `拉一下最新的`,
  `更新到最新`, `跟 main 对齐` and `更新一下代码` are five phrases over about three
  branches, and pull-latest is written three times.
- **Dropped because** — `拉一下最新的` is the phrase the held-out case
  `chinese-pull-latest` (`同步一下，拉最新的`) lands on. Removing it is an edit aimed
  at a held-out case in the direction that breaks it, which is the one thing
  `evals/ITERATION.md` forbids outright. `更新到最新` and `更新一下代码` are the two
  that go instead; they carry no case of their own.
- **Do not re-propose as** — "collapse the three pull-latest phrases into one."
  The collapse is right and was made; which one survives is not free.

## Keep the first sentence and cut only the negation

- **Aimed at** — the smallest possible edit: delete "It never rebases a feature
  branch, never resolves a conflict, and never discards a local commit." and
  leave everything else.
- **Dropped because** — it cut 91 characters where the audit found 114 of slack,
  and it left the duplication inside the opening sentence untouched:
  "fast-forward the base branch, and report what diverged" is restated by
  "It only fast-forwards; anything diverged is reported". Deleting a negation and
  keeping the duplication it duplicated is half an edit.
- **Do not re-propose as** — "the description is already short enough after the
  negation goes."

## State the boundary positively *and* keep the `Not for` clause naming conflicts

- **Aimed at** — nervousness about the held-out case `resolve-conflict`. The
  candidate added "a conflict is reported, never resolved" beside a `Not for`
  clause that already ends "or resolving a merge conflict".
- **Dropped because** — that is the exact duplication the audit named, re-added
  under a different name, and it is an edit written to answer a held-out case.
  The boundary is stated once, in the `Not for` clause, and the holdout is what
  tells us whether once is enough.
- **Do not re-propose as** — "say it in both voices so the refusal cannot be
  missed."
