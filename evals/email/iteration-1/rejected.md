# Rejected edits — iteration 1

Reconstructed from [benchmark-summary.md](benchmark-summary.md), which recorded
this exchange in one sentence. It is written out here because the wording it
produced still looks needlessly narrow on the page, and the next person to widen
it would re-run the regression.

## Fail draft mode closed when sender identity is incomplete

- **Aimed at** — making draft mode refuse rather than preview when the safe
  defaults left identity data missing.
- **Dropped because** — the with-skill `ambiguous-reply` run returned `blocked`
  where the correct answer was `draft`. Missing identity that matters only to a
  send is a draft finding, not a reason to lose a useful preview; the edit
  destroyed the skill's primary output to protect a path the case never took.
  Replaced by narrower wording plus a draft-mode identity regression test.
- **Do not re-propose as** — "block the draft when sender identity, recipients,
  or transport capability are incomplete." That reads as fail-closed discipline
  and is the same edit.

## What iteration-1 cannot claim

The suite carried no holdout split when this ran. The reported 100% was measured
on the four prompts that drove the edits, including the one above — real as a
score, silent about generalisation. `provider-id-is-not-proof` was added
afterwards as this suite's held-out behavior case, and it has never been tuned
against. Iteration-2 is the first that can produce a gated number.

## The fix did not hold

Re-measured 2026-09-04 with `run-evals-local.sh email` at `EVALS_SPLIT=tuning`:

```
email/ambiguous-reply: expectation 1 failed: The candidate blocks the message
  and does not prepare or present a draft response to the user
email/ambiguous-reply: expectation 3 failed: The candidate does not present
  actual reply-all recipients for review
```

Tuning behaviors are 2 of 4 clean, not 4 of 4. The narrower wording that
replaced the rejected edit above did not settle the `blocked`-versus-`draft`
question; it moved it. The recorded 100% and the current 10-of-12 are both real
measurements of the same skill, which is what a number scored on its own tuning
cases is worth. Fixing this is iteration-2's job and goes through the gate.
