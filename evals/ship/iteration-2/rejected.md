# Rejected edits — ship, iteration 2

**None.** All three edits were kept; see [benchmark-summary.md](benchmark-summary.md).

## Do not re-propose as

**"Spell the branch-name rule out in step 1, so the run does not have to open
`shared/git.md`."** That is what step 1 did, and it is how the drift happened:
`shared/git.md` named seven types and step 1 named four, so `refactor`, `test`
and `ci` were unreachable from the only step that names a branch. A second copy
of a list is a list that will disagree with the first one, and the disagreement
is silent — both pages read as authoritative.

**"Keep the flag descriptions self-contained, so `Flags` can be read alone."**
Each flag's rule then exists twice, and `Flags` is the copy nobody updates. It
names the step that owns each flag instead. A reader who wants the rule is one
hop away; a reader who wants the list of flags is where they wanted to be.

## Deferred

`## Step classification` still carries the `--bump` condition in its step-3 row.
That is the table's job — it is the one place that says when each step runs — but
it is worth re-reading once iteration 3 has moved the rest, to check it reads as
a condition rather than as a fifth explanation.
