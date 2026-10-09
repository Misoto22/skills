# Reunite — iteration 1 gate

## The edits

Two replaces in `plugins/dev/skills/reunite/SKILL.md`:

1. "One conversation, one file": a union cannot fix a stale copy because the entry is already present, so it skips it; running reunite again is the fix, not a second rename.
2. "It never deletes on request": offer `--undo` for rows a run added; otherwise delete in the app and let the next run carry it.

A third candidate — giving the restart's cause in the Reporting section — was not made: that case already passed 2/2.

## Gate

| | Before | After |
| --- | --- | --- |
| tuning (5 measurable cases) | 7/10 | 8/10 |
| holdout | 1/2 | 2/2 |

Tuning rose and the holdout did not fall: kept.

`refuses-to-prune` went 1/2 → 2/2. `titles-reach-the-other-accounts` stayed 0/2: one sample now gives the "already present" reason, and both lost expectation 2 only because the judge would not accept `scripts/merge.py` as running reunite. That expectation was reworded to name the script after the gate ran, so the next iteration measures it fresh. `synthetic-sandbox-merge` was void in all three gated attempts and is unmeasured here.

Spend: 0.84 CNY actual for the after phase across both skills; the shared ledger also holds four untrusted reservations from voided runs, which the gateway never priced.

n = 2 samples per case. This gate can veto; it cannot rank.
