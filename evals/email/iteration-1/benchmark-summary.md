# Email skill benchmark — iteration 1

The same four prompts ran once without the skill and once with the skill. Grading used 12 objective expectations.

| Configuration | Passed | Total | Pass rate |
| --- | ---: | ---: | ---: |
| Without skill | 9 | 12 | 75% |
| With skill | 12 | 12 | 100% |

The differentiating checks were cross-domain required-CC handling and the full regeneration/validation response to a Humanizer protected-fact change. The initial with-skill ambiguous-reply run overused `blocked`; a draft-mode identity regression test and narrower wording corrected it, and the fresh rerun passed all three expectations.

Verbatim outputs, grading JSON, timing metadata, generated benchmark data, and the static review page are kept in the sibling `skills-workspace/iteration-1` workspace. Runtime token and duration values were not exposed by the collaboration completion notifications, so those metrics are explicitly unmeasured.
