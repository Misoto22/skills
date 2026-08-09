---
name: bazi-compatibility-reading
description: Interpret a completed BaZi compatibility JSON artifact or equivalent verified comparison as a balanced, directional, evidence-linked relationship report. Use after the compatibility calculator or when asked to explain general, romance, marriage, friendship, family, or work scores already computed for two charts. Not for raw birth records, one-person readings, recalculation, predictions, or a binary destiny verdict.
license: MIT
metadata:
  version: "0.8.1"
---

# BaZi Compatibility Reading

Read one complete compatibility calculation and write `bazi_compatibility_reading_<name-a>_<name-b>.md`. Interpret its evidence; never recalculate either chart or any score.

## Route and validate

- Two raw birth records, two chart files, or one of each belong to `bazi-compatibility` first.
- One person's chart belongs to `bazi-reading`.
- Forecasts, auspicious dates, and event timing are outside this release.

Accept a `chinese-metaphysics.bazi-compatibility` JSON artifact at schema version 1 with a valid canonical checksum, or complete pasted equivalent data. Pasted data must include two names and chart checksums, model version, all five dimensions with weights/scores/ledgers, general score, optional contextual profile and score, confidence, and every sensitivity variant. Mark complete pasted input `pasted-complete`; do not claim checksum validation when none exists.

Use the vendored `shared/bazi/artifacts.py` validator for JSON. Stop on checksum mismatch, unsupported version, missing identity, wrong weights, incomplete positive or negative ledger, arithmetic mismatch, a contextual score without its profile, or an alternate range without variants. Name the defect and route source records to `bazi-compatibility`; never reconstruct a score.

## Evidence index before prose

Preserve the calculator's exact evidence and ownership:

- `[D-element]`, `[D-support]`, `[D-interactions]`, `[D-day-core]`, `[D-stability]` for dimensions.
- Preserve every dimension ledger id such as `[support.received.left]` and `[cross.branch_clash.day.month]`.
- `[G-score]` for the 25/20/20/20/15 general arithmetic.
- `[C-score]` for an explicitly selected contextual profile.
- `[S-primary-alternate]` style ids for sensitivity variants.

Every substantive claim cites evidence inline. Directional claims must name giver and receiver exactly as stored. Deduplicate the final index. Shen Sha may appear only when present in complete source evidence, with `[SS-...]` and `secondary` labels; it never explains a numeric dimension.

## Reading discipline

- Scores are versioned heuristics, not probabilities, success rates, scientific measurements, or predictions.
- General score remains primary. A contextual score answers only the explicitly named romance, marriage, friendship, family, or work lens.
- Do not invent context from names, genders, or a vague request. If `relationship_type` is null, omit the selected-context analysis rather than guessing.
- Preserve multidimensional disagreement. High affinity with low stability, or high complementarity with asymmetric support, must remain two findings rather than collapse into “compatible” or “incompatible.”
- Treat stem/branch combinations as ease or linkage hypotheses and clashes, harms, or breaks as friction hypotheses. Neither is automatically good or bad outside its ledger context.
- Describe asymmetry directly: what A supplies B can differ from what B supplies A. Do not turn unequal support into moral blame or a hierarchy.
- Use conditional language: “in this traditional model,” “may be experienced as,” and “suggests a discussion point.”
- Do not say soulmate, destined, karmically bound, toxic, safe/unsafe, marry/divorce, hire/fire, or predict duration, fidelity, abuse, fertility, money, health, or a future event.
- Give low-risk communication and boundary prompts, not medical, legal, financial, employment, or relationship commands.

## Sensitivity

The primary-primary general score is the displayed result. When alternates exist, explain the minimum, maximum, spread, and which source boundary changes. Do not average variants, select the best result, or describe the range as odds. Lower claim confidence when a major finding changes across variants.

## Required report order

Use the user's language and the matching headings in `references/output-template.md`. Keep exactly these eleven sections:

1. Basis and scope
2. Five-dimension scorecard
3. Element complement and drain
4. Directional support and asymmetry
5. Affinity and day-pillar core
6. Communication and coordination
7. Friction, conflict, and repair
8. Stability, confidence, and boundary sensitivity
9. Selected relationship context
10. Synthesis and practical prompts
11. Evidence index

Section 1 names both people, both source chart checksums, comparison checksum, model, source status, and heuristic disclaimer. Section 2 shows weights, scores, and general arithmetic without a binary verdict. Sections 3-8 use the relevant positive and negative ledgers. Section 9 says “not selected” when context is null. Section 10 gives three to five observable, reversible prompts and states what evidence each addresses. Section 11 maps every cited id to its exact source value and class.

## Write safely

Write UTF-8 Markdown only after validation. Use portable source names in `bazi_compatibility_reading_<name-a>_<name-b>.md` and preserve display names inside. Reuse an existing file only when it records the same compatibility checksum; otherwise append the first eight checksum characters. Do not overwrite another comparison, alter the source JSON, invoke chart calculation, or create new numeric scores.

Report both the reading path and source compatibility JSON path. See `references/examples.md` for asymmetric support, mixed dimensions, sensitivity, and corrupt-source handling.
