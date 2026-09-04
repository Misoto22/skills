---
name: bazi-compatibility-reading
description: Interpret a completed BaZi compatibility JSON artifact or equivalent verified comparison as a balanced, directional, evidence-linked relationship report. Use after the compatibility calculator or when asked to explain general, romance, marriage, friendship, family, or work scores already computed for two charts. Not for raw birth records, one-person readings, recalculation, predictions, or a binary destiny verdict.
license: MIT
metadata:
  version: "0.14.0"
---

# BaZi Compatibility Reading

Read one complete compatibility calculation and write `bazi_compatibility_reading_<name-a>_<name-b>.md` plus `bazi_compatibility_evidence_<name-a>_<name-b>.md`. Interpret its evidence; never recalculate either chart or any score. The first is a reader report; the second is a separate evidence artifact.

Before writing either file, read and follow `shared/report-presentation.md`. It defines the common localization, data-card, and separate-evidence boundary rules; this skill defines the compatibility evidence, direction, and section requirements.

## Route and validate

- Two raw birth records, two chart files, or one of each belong to `bazi-compatibility` first.
- One person's chart belongs to `bazi-reading`.
- Forecasts, auspicious dates, and event timing are outside this release.

Accept a `chinese-metaphysics.bazi-compatibility` JSON artifact at schema version 1 with a valid canonical checksum, or complete pasted equivalent data. Pasted data must include two names and chart checksums, model version, all five dimensions with weights/scores/ledgers, general score, optional contextual profile and score, confidence, and every sensitivity variant. Mark complete pasted input `pasted-complete`; do not claim checksum validation when none exists.

Validate a JSON artifact before interpreting a single score:

```bash
python3 scripts/validate_artifact.py COMPARISON.json
```

Exit 0 prints both names and the checksum to record. Exit 2 means stop, and prints every defect it found — a stale checksum, an unsupported version, a missing identity or chart checksum, a weight that disagrees with the declared model, a general or contextual score its own dimensions do not produce, a contextual score without its profile, a sensitivity range the displayed score sits outside. Name those defects and route the source records to `bazi-compatibility`; never reconstruct a score. A `pasted-complete` source has no artifact to run this against: hold it to the same fields by hand.

## Evidence index before prose

Preserve the calculator's exact evidence and ownership before writing prose:

- `[D-element]`, `[D-support]`, `[D-interactions]`, `[D-day-core]`, `[D-stability]` for dimensions.
- Preserve every dimension ledger id such as `[support.received.left]` and `[cross.branch_clash.day.month]`.
- `[G-score]` for the 25/20/20/20/15 general arithmetic.
- `[C-score]` for an explicitly selected contextual profile.
- `[S-primary-alternate]` style ids for sensitivity variants.

Use this index to build the evidence artifact's heading-based claim map. Compatibility mappings must also record the stored owner or direction. Do not expose raw ids or stored ownership labels in the reader report.

Reader-report directional claims must name both people in the form `Name A → Name B`; describe what A supplies or what B receives in plain language. Reserve stored `left` and `right` ownership labels for the evidence artifact. Shen Sha may appear only when present in complete source evidence, with `[SS-...]` and `secondary` labels in the evidence artifact; it never explains a numeric dimension.

## Reading discipline

- Scores are versioned heuristics, not probabilities, success rates, scientific measurements, or predictions.
- When a relationship context is explicitly selected, show its contextual score first in the reader layer and label the general score as a secondary reference. When `relationship_type` is null, show the general score as the displayed result. A contextual score answers only the explicitly named romance, marriage, friendship, family, or work lens.
- Do not invent context from names, genders, or a vague request. If `relationship_type` is null, omit the selected-context analysis rather than guessing.
- Preserve multidimensional disagreement. High affinity with low stability, or high complementarity with asymmetric support, must remain two findings rather than collapse into “compatible” or “incompatible.”
- Treat stem/branch combinations as ease or linkage hypotheses and clashes, harms, or breaks as friction hypotheses. Neither is automatically good or bad outside its ledger context.
- Describe asymmetry directly: what A supplies B can differ from what B supplies A. Do not turn unequal support into moral blame or a hierarchy.
- Use conditional language: “in this traditional model,” “may be experienced as,” and “suggests a discussion point.”
- Do not say soulmate, destined, karmically bound, toxic, safe/unsafe, marry/divorce, hire/fire, or predict duration, fidelity, abuse, fertility, money, health, or a future event.
- Give low-risk communication and boundary prompts, not medical, legal, financial, employment, or relationship commands.

## Sensitivity

The primary-primary calculation supplies the displayed score: show its contextual score first when a context is selected, or its general score when `relationship_type` is null. When alternates exist, explain the minimum, maximum, spread, and which source boundary changes. Do not average variants, select the best result, or describe the range as odds. Lower claim confidence when a major finding changes across variants.

## Required report order

Keep exactly these six reader-report sections, using the structure in `references/output-template.md`:

1. Relationship pattern
2. What draws the pair together
3. Main misalignment
4. Each person's likely experience
5. What to observe now
6. Model data card

Lead with a conditional relationship pattern, but do not lead with score, source confidence, or a method disclaimer. Develop the attraction, friction, and two directional experiences to the depth required by `shared/report-presentation.md`; do not reduce the reader report to a score summary. Use sections 2–5 to preserve mixed dimensions, explain named directional support, and offer low-risk observations. When a relationship context is explicitly selected, show its contextual score first in section 6 and label the general score as a secondary reference; otherwise show the general score and state that no context was selected. Do not invent a context.

In section 4, describe each person's likely experience separately using `Name A → Name B` direction labels, never stored `left` or `right` labels. Section 5 gives no more than three observable, reversible prompts. Keep the data card small: the displayed score and no more than three supporting indicators.

Write the separate evidence artifact after the reader report. In addition to the shared evidence requirements, include source status, both source-chart checksums, the comparison checksum when available, exact five-dimensional weights and values, general and contextual weighted arithmetic, confidence, sensitivity variants, and stored owner or direction for compatibility evidence.

## Optional ink-wash poster

Offer a poster only when the couple asks for a visual, shareable, or printable report. It never replaces the reader report or the evidence artifact.

Read `shared/divination-report/poster-contract.md`, write the payload as data only, and render it:

```bash
python3 shared/divination-report/render_poster.py --data POSTER_PAYLOAD.json --out bazi_compatibility_poster_NAMES.html
```

Fill `meta.system_label` with 八字合参, show the displayed primary score and at most three supporting indicators in `core_metrics`, and use `domains.rows` for the dimension comparison with one `readings` entry per person. Put every recorded tension in `conflicts.rows`; a poster that shows only the favourable dimensions is a failed poster. Set `footer.evidence_link` to the evidence artifact filename. Never write the HTML yourself and never edit the template for one reading.

## Write safely

Write UTF-8 Markdown only after validation. Use portable source names in `bazi_compatibility_reading_<name-a>_<name-b>.md` and `bazi_compatibility_evidence_<name-a>_<name-b>.md`; preserve display names inside both files. Reuse an existing report pair only when both record the same compatibility checksum; otherwise append the first eight checksum characters to both names. Do not overwrite another comparison, alter the source JSON, invoke chart calculation, or create new numeric scores.

Report the reader-report path, evidence-artifact path, and source compatibility JSON path. See `references/examples.md` for asymmetric support, mixed dimensions, sensitivity, and corrupt-source handling.
