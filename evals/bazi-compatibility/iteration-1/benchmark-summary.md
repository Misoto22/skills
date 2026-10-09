# BaZi compatibility — iteration 1 gate

## The edits

1. The rules-file reference is now a markdown link, `[shared/rules/compatibility-v1.json](shared/rules/compatibility-v1.json)`. An agent follows it, and the evaluation harness includes linked `.json` in the prompt — the single source stays single and becomes reachable.
2. A time given only to the hour (早上七点, 7am) is not an exact minute: ask for it rather than reading it as 07:00.

## Gate

| | Before | After |
| --- | --- | --- |
| tuning | 3/6 | 5/6 |
| holdout | 1/2 | 2/2 |

Kept. `score-contract` 0/2 → 2/2 (edit 1), `missing-minute` 1/2 → 2/2 (edit 2). `automatic-handoff` went 2/2 → 1/2.

**Configuration differs between phases for the execution cases:** after edit 1 the linked rules file plus tool output exceeded the 64k input cap and every after-phase sample of `alternate-range` voided on `candidate_context_limit`; both execution cases were re-run at 128k. The before phase ran at 64k. The tuning rise comes from the two text cases, which ran identically; the execution-case numbers are recorded, not credited.

n = 2 per case.
