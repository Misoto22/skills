# Rejected edits — sync, iteration 1

**None.** Both edits were kept; see [benchmark-summary.md](benchmark-summary.md).

An iteration whose edits all passed the gate is a small iteration, not a
well-designed one. This one renamed two cross-references and changed no rule, so
there was nothing for the gate to reject.

## Deferred, not rejected

`ahead-behind-not-transposed` fails on both of its last two expectations, at
baseline and after. They ask the runner to produce counts from a repository it
cannot see. That is a case defect of the kind `evals/README.md` describes, and
fixing it belongs in its own change — a case rewritten while an edit is open
cannot tell a fix from an overfit.
