# Rejected edits — iteration 4

Two candidates dropped, both on a static reading of the suite rather than on a
score.

## Drop `把这些改动提上去` as a duplicate of `推上去合并`

- **Aimed at** — the audit's "one trigger per branch". The two phrases are both
  push-then-merge, eight characters apart.
- **Dropped because** — `把这些改动提上去` is what `sync`'s tuning non-trigger
  `chinese-push-up` (`把这些改动提上去合了`) hands off to. That case asserts `ship`
  wins a prompt using `提上去`, and `推上去合并` uses a different verb. Dropping it
  would have been an edit to `ship` that fails a case in `sync`'s suite — the
  failure mode `check-descriptions.py` exists for, arriving from the other side.
- **Do not re-propose as** — "`推上去合并` already covers pushing." It covers one
  of the two verbs Chinese uses here.

## Also drop the "push this up and merge" English trigger

- **Aimed at** — hitting the 100-150 character target exactly, after removing
  the preflight sentence had already cut 129.
- **Dropped because** — it is padding a number by deleting a branch. Nothing in
  the suite lands on it today, but it is the English pair of `推上去合并`, and the
  Chinese pair is load-bearing. Removing it to reach a character count would be
  optimising the measurement rather than the description.
- **Do not re-propose as** — "no case needs it, so it costs nothing to remove."
  No case needing a trigger is not the same as no prompt using it; the suite is
  a sample.
