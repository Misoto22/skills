# Steward — iteration 1 gate

## The edits

- **SKILL.md, one replace:** the per-repository table example now shows `failed: gh unauthenticated` in the Synced column. §6 already said a failed pass is reported as `failed: <reason>`, but the only example listed `ff 3 · up to date · skipped: dirty`, and earlier drafts copied it into a failed repository's row.
- **Case correction, not a skill edit:** `merge-ledger-without-merging` now names the failing check (`test (3.13)`) in its prompt, so the expectation "names the failing check" is answerable.

## Gate

| | Before | After |
| --- | --- | --- |
| tuning | 3/12 | 9/12 |
| holdout | 1/2 | 1/2 |

Tuning rose and the holdout did not fall: kept. The rise is larger than one table row can account for. `merge-ledger-without-merging` (0 → 2) moved with its corrected prompt, and `occupied-worktree-kept`, `unattended-proposes-titles-only` and `vanished-checkout-continues` moved 1 → 2 without an edit aimed at them: at n = 2 that is sampling noise, and it is recorded as such rather than credited to the edit.

`one-repository-failing-does-not-stop-the-sweep` stayed 0/2 on expectation 3 alone; it was reworded after the gate ("naming the command for the person to run later is expected"). `schedule-on-request` went 0/2 → 1/2 and remains a case a text-only run cannot fully satisfy.
