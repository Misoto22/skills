# Rejected edits — ship, iteration 3

**None.** Both edits were kept; see [benchmark-summary.md](benchmark-summary.md).
The third budgeted edit was not spent — this iteration is the tail of a three-way
split, not a full one.

## Do not re-propose as

**"Bring the marker tables back into 0e–0h so the preflight can be read in one
pass."** The preflight *is* read in one pass; what moved out is the lookup it
consults, not the step that consults it. Seventy-seven lines of tables sat
between step 0d and step 0i, so the run's own sequence was interrupted by
reference material four times over. 0e–0h still say what to record and which
later step acts on it, which is the part the sequence needs.

**"Repeat the version-string rationale in `Reporting`, since that is where the
`Attention` line is written."** `Reporting` already lists `version not bumped`
among the things `Attention` carries. The reason a silent skip is dangerous
belongs where the decision is made, in 0h, and it was the sixth statement of the
same paragraph before this edit.

## Deferred

`references/detection.md` is reached by three pointers, one per detected thing.
A single pointer from a combined 0e–0h heading would be one line rather than
three, but it would also renumber the sub-steps, and 2a, 2b, 3a and 5 all name
them. Worth doing only alongside that renumbering, not on its own.
