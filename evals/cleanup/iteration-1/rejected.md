# Rejected edits — cleanup, iteration 1

**None.** All three edits were kept; see [benchmark-summary.md](benchmark-summary.md).

## Do not re-propose as

**"Restate the rule after citing it, in case the heading is not read."** That is
the shape this iteration removed. `cleanup` opened by pointing at
`shared/git.md` and then wrote out three of its rules again — the home worktree,
what deleting a remote branch does to an open pull request, and what `git mv`
leaves behind. Two copies of a rule are not twice as reliable; they are one rule
that can be corrected in one place and go on being taught wrongly from the other.
If a citation measurably loses a behaviour, the fix is a sharper heading or a
sharper pointer, not a second copy.

## Deferred

One restatement survives, in step 1: *`-d` refuses after a rebase merge, for the
reason in `shared/git.md`; `-D` is correct here precisely because the SHAs were
rewritten.* It cites and then restates, like the three that went. It is left
because the clause is one line at the point of use and the edit budget was spent
on the three-paragraph copies. Worth taking in a later iteration.
