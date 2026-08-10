# BaZi report readability design

## Goal

Make natal and compatibility readings immediately understandable in the user's language while preserving the existing verified calculation and audit trail. The calculation artifacts, schemas, scores, and checksums remain unchanged.

## Output architecture

Use one Markdown report with two visual layers:

1. A reader layer containing the conclusion, chart overview, score summary, interpretation, and practical prompts.
2. A final technical appendix containing full checksums, model ids, exact arithmetic, unrounded values, and raw ledger ids.

The reader layer uses only the user's language. It cites compact numbered markers such as `〔1〕`; the appendix maps each marker to exact source values and raw evidence ids. Full checksums and raw ids never appear in reader-facing prose.

## Natal report

Replace the ten audit-first sections with seven reader-first sections:

1. Conclusion at a glance
2. Chart overview
3. Element and day-master summary
4. Core structure
5. Strengths and tensions
6. Relationship, work, and reflection prompts
7. Technical basis and evidence

Use concise tables for the four pillars and score overview. Show rounded display values in the reader layer and exact values in the appendix.

## Compatibility report

Replace the eleven audit-first sections with eight reader-first sections:

1. Conclusion at a glance
2. Two-chart overview
3. Relationship scorecard
4. Three core findings
5. Each person's likely experience
6. Strengths, friction, and repair
7. Practical prompts
8. Technical basis and evidence

Show the selected relationship-context score first when present and label the general score as a secondary reference. Write direction as `Name A → Name B`; never expose `left` or `right` outside the appendix. Display scores as whole numbers in the reader layer and retain exact decimals and weighted arithmetic in the appendix.

## Boundaries and failure handling

Keep all source validation, checksum refusal, alternate-chart handling, non-probability language, and prohibited deterministic claims unchanged. If an exact value is needed to explain sensitivity or a boundary, it may appear in the reader layer in plain language. Raw identifiers remain appendix-only.

## Verification

Add behavior cases for Chinese-only labels, conclusion-first order, compact evidence markers, appendix-only technical identifiers, contextual-score priority, and explicit directional names. Forward-test the revised skills against the Henry and Cindy artifacts, then run evaluation, repository, formatting, lint, and unit-test checks.
