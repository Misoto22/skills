# Compatibility reading examples

## High affinity, lower stability

Good reader-layer synthesis: “日柱核心显示较强的连结线索，而稳定性维度同时保留了未解决结构与内部互动压力。〔1〕〔2〕 在这个传统模型中，亲近感与压力下的持续协作是不同的问题；前者可视为连结资源，后者则提示可以把修复习惯说清楚。〔1〕〔2〕”

The final technical appendix maps `〔1〕` to `[D-day-core]` and `〔2〕` to `[D-stability]`, with their exact values. The reader layer does not show raw ids.

Bad synthesis: “The total is high, so the relationship will work.”

## Directional asymmetry

For this example, the artifact stores 甲 as `left` and 乙 as `right`. Each `support.received.*` entry is owned by its receiver, so `甲 → 乙` maps to `[support.received.right]`, the entry owned by 乙, while `乙 → 甲` maps to `[support.received.left]`, the entry owned by 甲.

Good reader-layer wording: “甲 → 乙：乙可能从甲那里接收到较强的资源或同侪式支持；乙 → 甲：甲可能从乙那里接收到的同类支持较少。〔1〕〔2〕 这不是高低排名，而是提示双方可以核对：各自重视的支持是否被看见，并以对方能感受到的方式回应。〔1〕〔2〕”

The final appendix maps `〔1〕` to `[support.received.right]` with stored owner 乙 and provider 甲, and maps `〔2〕` to `[support.received.left]` with stored owner 甲 and provider 乙. Do not write `left` or `right` in reader prose.

Bad: “B is the giver and A is dependent.”

## Context

When the source declares `work`, show the separately reweighted work index first in the reader layer, then label the unchanged general score as a secondary reference. Cite both with compact markers and retain `[C-score]`, `[G-score]`, and exact arithmetic in the appendix. Do not import romance or marriage language.

When context is null, state that no relationship context was selected. “Selected relationship context: not selected.” is an English example only; translate it into the user's language. Do not choose a context from the names or score pattern.

## Alternate sensitivity

Good reader-layer wording: “主版本是本报告的展示结果。〔1〕 边界变化会让分数在记录的最低与最高结果之间移动，因此跨越类别的日柱核心结论暂不下定论。〔1〕” Put the exact minimum、maximum、spread, changed source boundary, and `[S-primary-alternate]` values in the final appendix.

Bad: use the maximum as “potential” or average the range.

## Corrupt source

Refuse a changed or incomplete artifact: name the checksum or ledger defect, do not use its Markdown as a substitute, and route the original two sources back to `bazi-compatibility`.
