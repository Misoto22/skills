---
name: bazi-compatibility-reading
description: Interpret a completed BaZi compatibility JSON artifact or equivalent verified comparison as a balanced, directional, evidence-linked relationship report. Use after the compatibility calculator or when asked to explain general, romance, marriage, friendship, family, or work scores already computed for two charts. Not for raw birth records, one-person readings, recalculation, predictions, or a binary destiny verdict.
license: MIT
metadata:
  version: "0.8.2"
---

# BaZi Compatibility Reading

Read one complete compatibility calculation and write `bazi_compatibility_reading_<name-a>_<name-b>.md`. Interpret its evidence; never recalculate either chart or any score.

Before writing the report, read and follow `shared/report-presentation.md`. It defines the common localization, compact-citation, rounded-display, and technical-appendix boundary rules; this skill defines the compatibility evidence, direction, and section requirements.

## Route and validate

- Two raw birth records, two chart files, or one of each belong to `bazi-compatibility` first.
- One person's chart belongs to `bazi-reading`.
- Forecasts, auspicious dates, and event timing are outside this release.

Accept a `chinese-metaphysics.bazi-compatibility` JSON artifact at schema version 1 with a valid canonical checksum, or complete pasted equivalent data. Pasted data must include two names and chart checksums, model version, all five dimensions with weights/scores/ledgers, general score, optional contextual profile and score, confidence, and every sensitivity variant. Mark complete pasted input `pasted-complete`; do not claim checksum validation when none exists.

Use the vendored `shared/bazi/artifacts.py` validator for JSON. Stop on checksum mismatch, unsupported version, missing identity, wrong weights, incomplete positive or negative ledger, arithmetic mismatch, a contextual score without its profile, or an alternate range without variants. Name the defect and route source records to `bazi-compatibility`; never reconstruct a score.

## Evidence index before prose

Preserve the calculator's exact evidence and ownership before writing prose:

- `[D-element]`, `[D-support]`, `[D-interactions]`, `[D-day-core]`, `[D-stability]` for dimensions.
- Preserve every dimension ledger id such as `[support.received.left]` and `[cross.branch_clash.day.month]`.
- `[G-score]` for the 25/20/20/20/15 general arithmetic.
- `[C-score]` for an explicitly selected contextual profile.
- `[S-primary-alternate]` style ids for sensitivity variants.

Apply the compact-citation and appendix-mapping contract in `shared/report-presentation.md` to this index. Compatibility mappings must also record the stored owner or direction.

Reader-layer directional claims must name both people in the form `Name A → Name B`; describe what A supplies or what B receives in plain language. Reserve stored `left` and `right` ownership labels for the final appendix. Shen Sha may appear only when present in complete source evidence, with `[SS-...]` and `secondary` labels in the appendix; it never explains a numeric dimension.

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

Keep exactly these eight sections, using the structure in `references/output-template.md`:

1. Conclusion at a glance
2. Two-chart overview
3. Relationship scorecard
4. Three core findings
5. Each person's likely experience
6. Strengths, friction, and repair
7. Practical prompts
8. Technical basis and evidence

Make sections 1–7 the reader layer. State the conditional conclusion, material uncertainty, and heuristic scope disclaimer first. In section 2, show both people and a concise two-chart overview. In section 3, show all five dimensions. When a relationship context is explicitly selected, show its contextual score first and label the general score as a secondary reference; otherwise show the general score and state that no context was selected. Do not invent a context.

Use sections 4–6 to preserve mixed dimensions, explain named directional support, and pair friction with low-risk repair hypotheses. In section 5, describe each person's likely experience separately using `Name A → Name B` direction labels, never stored `left` or `right` labels. Section 7 gives three to five observable, reversible prompts and states which compact marker each addresses.

Make section 8 the final audit appendix. In addition to the shared appendix requirements, include source status, both source-chart checksums, the comparison checksum when available, exact five-dimensional weights and values, general and contextual weighted arithmetic, confidence, sensitivity variants, and stored owner or direction for compatibility evidence.

## Write safely

Write UTF-8 Markdown only after validation. Use portable source names in `bazi_compatibility_reading_<name-a>_<name-b>.md` and preserve display names inside. Reuse an existing file only when it records the same compatibility checksum; otherwise append the first eight checksum characters. Do not overwrite another comparison, alter the source JSON, invoke chart calculation, or create new numeric scores.

Report both the reading path and source compatibility JSON path. See `references/examples.md` for asymmetric support, mixed dimensions, sensitivity, and corrupt-source handling.
