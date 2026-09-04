# Gate — iteration 1

**The gate did not run.** One edit is kept anyway, on evidence that does not come
from a score. This file says which part is measured and which is not, because an
unmeasured edit presented as a gated one is the failure this whole loop exists to
prevent.

## The edit

`plugins/astrology/skills/synastry-reading/SKILL.md`, one replace in the drafting
rules. It writes down the two things `validate_reading.py` enforces and the skill
never states:

- a citation is the bracketed token that opens a ledger entry — `[E-ASPECT-9DAF]`,
  `[E-OVERLAY-3096]` — copied character for character, and the display string
  beside it is not a substitute;
- "conditional" means the paragraph carries one of `can`, `could`, `may`,
  `might`, `tends`, `often`, `suggests`, `appears`, `possibly`, `perhaps`,
  `potentially`, or 可能, 也许, 或许, 倾向, 往往, 通常, 有时, 似乎, while `will`,
  `shall`, `guarantees`, `destined`, `definitely`, `inevitably`, `certain to`,
  `must happen`, `going to`, 必然, 注定, 保证, 一定会, 肯定会 and 必定 are refused
  wherever they appear, including in prose that was never meant as a forecast.

## What is measured, and what is not

**Measured, and it needs no gateway.** `[E-ASPECT-` appears in
`validate_reading.py` as a hard requirement and appears nowhere in `SKILL.md` or
in any of its three references. `output-template.md` writes `<Conditional
synthesis with inline evidence ID(s).>`, which tells a model to cite and leaves
the form to guess. That is a static fact about the repository, checkable with
grep, and it is the whole basis for keeping this edit: the document does not
state what its own validator enforces.

**Not measured.** Whether stating it changes the score. Four attempts:

| attempt | outcome |
| --- | --- |
| full scan, 2026-09-04 | 2 cases scored (both FAIL, mechanical), 3 lost to the 120-second proxy window, 1 pass |
| after streaming landed | 1 holdout case scored; no pre-edit baseline existed to compare it to |
| before/after run 1 | gateway began returning `404 page not found` mid-run; every AFTER case 404'd |
| before/after run 2 | same, after one baseline case |

The gateway serves roughly one long generation and then returns 404 for a
stretch. `8b7f081` fixed the 120-second proxy window and that part now works —
a case that had burned nine minutes into a 524 scores in three and a half. The
404 burst is a different fault and it is upstream of anything in this repository.

**Baseline data points that did survive**, both pre-edit, both mechanical:

```
explicit-family-and-work-context   lacks valid evidence; requires conditional
                                   language; measurement does not match paragraph
                                   evidence; claim does not match paragraph evidence
neutral-context-omits-sensitive-domains
                                   deterministic prediction language; lacks valid
                                   evidence; requires conditional language;
                                   measurement does not match paragraph evidence
```

Both are exactly the violations the edit addresses. Neither has an after.

## What this iteration may not claim

That the edit works. `evals/ITERATION.md` keeps an edit when tuning rose and the
holdout did not fall, and neither half of that sentence has a number behind it
here. What is claimed is narrower and true: the skill now states the format its
validator requires, which it previously did not.

Iteration-2 opens on the measurement, not on a new edit. Re-run both splits when
the gateway holds a full pass, and record the numbers here.
