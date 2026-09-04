# Rejected edits — iteration 3

**None.** Both edits were kept; see [benchmark-summary.md](benchmark-summary.md)
for the arithmetic and for how thin the margin is.

## Deferred, not rejected — do re-propose this

One of the three budgeted edits was left unspent, and the next iteration should
spend it here rather than rediscovering the problem.

**Disambiguate "remove the active sender" in step 3 of the workflow.** It means
the current user, who must never appear in their own recipient list. A model can
read it as the sender of the message being replied to, which is backwards: on a
reply-all that person is the To recipient, and dropping them produces a reply
that never reaches the person being answered.

Observed once, in the final sample of this iteration's gate run:

> The candidate lists only purchasing@acme.test, finance@acme.test, and
> ops@thirdparty.test as reply-all candidates, and does not present the original
> sender ops@supplier.test as a reply-all recipient.

It was not fixed here because it appeared with no budget left to measure a fix
against `ambiguous-reply`'s background flakiness — the case passes about two runs
in three regardless of what the skill says, which is the other thing iteration-4
has to deal with. Consider whether that flakiness is the case carrying five
assertions in three expectations rather than the skill being unstable.
