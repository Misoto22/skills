# Slop audit report template

Fill every section. Replace `…` with findings; keep the headings.

```markdown
# Slop audit — <repository> — <YYYY-MM-DD>

## Do these first
1. <proposal> — <time estimate> — enforces <rule> — <removes N current violations | adds N new checks>
2. …
3. …

## Scorecard
| # | Check | Layer | Score | Evidence |
|---|-------|-------|-------|----------|
| 1 | Corrections become checks | static | | |
| 2 | Nuanced APIs fenced | static | | |
| 3 | Architecture visible in paths | code | | |
| 4 | No workaround justifications | code | | |
| 5 | Feature map | verification | | |
| 6 | Agents run and observe the app | verification | | |
| 7 | Reviewable state model | verification | | |
| 8 | Invariants as properties | verification | | |
| 9 | Trust metrics | automation | | |
| 10 | Outer loop readiness | automation | | |

Total: <sum of numeric scores>/<2 × numeric checks> · Average of 1–8: <x.xx>
Not scored: <check: n/a | not assessed | blocked — reason>, or none
Not run locally: <enforcers whose state comes from CI>, or none

## Findings by check
### <n>. <check name> — <score>
- Gaps (ranked by recurrence): …
- Proposal: <file to change> · <installed tool> · <check that will enforce it>

## Prose that should become checks
| Rule (owning source file:line) | Proposed enforcement | Violations now |
|---|---|---|
```

Cite a rule at the file that owns it: when `AGENTS.md` or `CLAUDE.md` is generated, cite the source it is generated from.
