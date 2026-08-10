# Compatibility reading examples

## High affinity, lower stability

Good reader-report synthesis: “你们之间有靠近和配合的线索，但在压力下未必会自然用同一种方式处理问题。这个传统模型提示：亲近感和长期协作是两件需要分别观察的事。”

Write the exact day-core and stability values, raw ids, and the heading-based claim map in the separate evidence artifact. Do not put numbered citations or raw ids in reader prose.

Bad synthesis: “The total is high, so the relationship will work.”

## Directional asymmetry

For this example, the artifact stores 甲 as `left` and 乙 as `right`. Each `support.received.*` entry is owned by its receiver, so `甲 → 乙` maps to `[support.received.right]`, the entry owned by 乙, while `乙 → 甲` maps to `[support.received.left]`, the entry owned by 甲.

Good reader-report wording: “甲 → 乙：乙可能更容易从甲的主动、落实或回应中感受到支持；乙 → 甲：甲未必总能从乙给出的方式里直接感到被支持。这不是高低排名，而是提醒双方核对：自己表达的在意，是否正好是对方收得到的。”

The separate evidence artifact records both raw ids, stored owner/provider, exact values, and the claim-map entry. Do not write `left` or `right` in reader prose.

Bad: “B is the giver and A is dependent.”

## Context

When the source declares `work`, show the separately reweighted work index first in the model data card, then label the unchanged general score as a secondary reference. Keep `[C-score]`, `[G-score]`, and exact arithmetic in the evidence artifact. Do not import romance or marriage language.

When context is null, state that no relationship context was selected. “Selected relationship context: not selected.” is an English example only; translate it into the user's language. Do not choose a context from the names or score pattern.

## Alternate sensitivity

Good reader-report wording: “主版本是本报告的展示结果；边界变化会影响部分结论，因此跨越变化边界的判断暂不下定论。” Put exact minimum, maximum, spread, changed source boundary, and `[S-primary-alternate]` values in the evidence artifact.

Bad: use the maximum as “potential” or average the range.

## Corrupt source

Refuse a changed or incomplete artifact: name the checksum or ledger defect, do not use its Markdown as a substitute, and route the original two sources back to `bazi-compatibility`.
