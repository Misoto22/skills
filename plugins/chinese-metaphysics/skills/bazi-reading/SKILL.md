---
name: bazi-reading
description: Interpret a completed single-person BaZi JSON chart or equivalent verified four-pillar data as an evidence-linked static natal report. Use when a calculator hands off its artifact or someone asks to 解读八字, 看命局, explain day-master strength, structure, or favorable elements from an existing chart. Not for raw birth details, relationship matching, luck cycles, dated predictions, or incomplete source data.
license: MIT
metadata:
  version: "0.8.1"
---

# BaZi Reading

Read one complete chart and write `bazi_reading_<name>.md`. Interpret; never recalculate.

## Route and source gate

- Raw name/place/date/time belongs to `bazi-chart` first.
- Two-person matching belongs to `bazi-compatibility`.
- Da Yun, annual luck, dated events, and forecasts are outside this release.

Accept one of:

1. A `chinese-metaphysics.bazi-chart` JSON artifact at schema version 1 with a valid canonical checksum.
2. Its verified Markdown rendering together with the matching JSON. Markdown alone is not a machine source.
3. Complete pasted equivalent data containing identity, all four pillars and boundaries, facts, interaction records, both score distributions, day-master ledger, model versions, confidence, and alternate sensitivity. Mark this source `pasted-complete`; do not pretend it had a checksum.

Use the vendored `shared/bazi/artifacts.py` validator for a JSON artifact. Stop on checksum mismatch, unsupported schema/version, a missing hour pillar, an incomplete score ledger, or a sensitivity flag without a complete alternate. Name the exact defect and route raw details back to `bazi-chart`; never patch or infer a field.

## Build an evidence ledger first

Assign stable report references before writing prose:

- `[P-year]`, `[P-month]`, `[P-day]`, `[P-hour]` for primary pillars.
- `[B-year]`, `[B-month]`, `[B-day]`, `[B-hour]` for boundary and time basis.
- Preserve each structural interaction id such as `[interaction-001]`.
- Preserve scoring ids such as `[base.visible.month]`, `[adjust.seasonal.木]`, and strength component names.
- Prefix alternate evidence with `[ALT-...]`.
- Prefix Shen Sha with `[SS-...]` and label it secondary.

Every substantive sentence must cite one or more of these references inline. Deduplicate the evidence index: one id, one source fact. If evidence conflicts, describe the tension instead of selecting the more flattering result.

## Interpretation discipline

- Say “in this traditional model,” “suggests,” or “is commonly read as.” Never present metaphysical interpretation as scientific fact, certainty, diagnosis, or fate.
- Explain five-element percentages and the day-master score as outputs of the named heuristic model, not probabilities.
- Start from month command, day master, roots, visible support/control, and formed structural relations. A score does not establish a special structure by itself.
- Treat favorable and unfavorable tendencies as conditional balancing hypotheses tied to the ledger, not universal prescriptions.
- Keep Shen Sha secondary; no single Shen Sha may drive a conclusion.
- Do not infer gender or apply gender-dependent conventions unless the source explicitly supplies gender and the user requests that convention.
- Do not infer personality disorders, health conditions, fertility, lifespan, wealth amount, moral character, or inevitable relationship outcomes.
- Give practical actions as low-risk reflection prompts, not commands to make medical, legal, financial, employment, or relationship decisions.

## Alternate-chart sensitivity

When a 00:00-boundary alternate exists, interpret primary and alternate independently. Separate:

- stable findings supported by both charts;
- changed day/hour evidence and every conclusion it affects;
- claims that should be withheld because the boundary choice changes them.

Never average their pillars, percentages, strength scores, or interpretations. Lower the report's claim confidence where sensitivity is material.

## Required report order

Use the user's language and the matching headings in `references/output-template.md`. Keep exactly these ten sections:

1. Basis and boundaries
2. Score overview
3. Day master and month command
4. Structure and favorable tendencies
5. Strengths and tensions
6. Behavioral patterns
7. Relationship patterns
8. Work and contribution
9. Practical reflection prompts
10. Evidence index

Section 1 must name source status, primary pillars, true-solar and day-boundary rules, models, confidence, and alternate sensitivity. Section 2 must show the numeric outputs with the heuristic disclaimer. Sections 3-9 must cite evidence inline. Section 10 maps every used id to exact source data and says whether it is primary, calculated heuristic, alternate, or secondary Shen Sha evidence.

## Write safely

Create UTF-8 Markdown only after validation and evidence indexing. Use the portable source name in `bazi_reading_<name>.md`; preserve the display name inside the report. Do not overwrite a different existing report. When a same-name file already exists, reuse it only if its recorded source checksum matches; otherwise append the first eight checksum characters.

Report the reading path and source JSON path. Do not create new chart JSON, alter the source artifact, or invoke the chart calculator after a valid hand-off.

See `references/examples.md` for a hand-off, alternate-boundary treatment, and corrupt-source refusal.
