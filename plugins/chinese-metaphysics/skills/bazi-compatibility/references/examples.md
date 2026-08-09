# BaZi compatibility workflow examples

## Reuse two charts

Put each verified chart path under `left.chart_path` and `right.chart_path`. The command validates both checksums and compares their existing facts and scores without invoking either natal reading or chart calculator.

## Mix one chart with one raw record

Use `left.chart_path` and `right.birth`. Resolve the raw record to an exact `<YYYY-MM-DD>`, `<HH:MM>`, place, coordinates, and IANA zone first. Only the raw side is calculated.

## Relationship-neutral default

“Are A and B compatible?” does not establish romance, marriage, friendship, family, or work. Omit `relationship_type`; report the general index only.

“A and B are cofounders; compare how they work together” establishes `work`. Keep the unchanged general index and add the work contextual index.

## Boundary sensitivity

If one source contains an alternate, the output may show primary-primary, primary-alternate, alternate-primary, or alternate-alternate variants. Treat the minimum and maximum as sensitivity, not as odds or a forecast.

## Failure cases

- Modified chart checksum: stop; do not trust the Markdown or recalculate silently.
- Missing minute on one raw side: request it; do not compare one complete chart with one approximate chart.
- Unknown context such as `soulmate`: reject it; do not invent a profile.
