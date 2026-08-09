# BaZi reading examples

## Valid calculator hand-off

Input: a verified chart JSON path from `bazi-chart`.

Good opening: “The source checksum validates. The primary pillars are … `[P-year]` `[P-month]` `[P-day]` `[P-hour]`. The calculation uses true solar time, exact `jie` boundaries, and a 23:00 day boundary `[B-day]`. Numeric values below are `bazi-score-v1` heuristic outputs, not probabilities.”

The report then uses facts such as “the month command applies the prosperous multiplier to Wood `[adjust.seasonal.木]`” instead of asserting an unsupported personality trait.

## Alternate boundary

Good treatment: “Both versions retain the same year and month basis, so the seasonal reading is stable `[P-month]` `[ALT-P-month]`. The day and hour pillars change under the midnight convention `[P-day]` `[ALT-P-day]`; therefore day-master-specific relationship claims are boundary-sensitive and are withheld.”

Bad treatment: average the two day-master scores or choose the more favorable chart.

## Corrupt source

Good refusal: “I cannot interpret this artifact because its checksum does not match its canonical content. I will not repair a pillar or score. Please restore the original JSON or rerun `bazi-chart` from the raw birth record.”

Bad response: trust the Markdown, reconstruct the missing hour pillar, or continue with a disclaimer.
