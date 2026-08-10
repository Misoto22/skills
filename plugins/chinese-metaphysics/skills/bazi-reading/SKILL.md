---
name: bazi-reading
description: Interpret a completed single-person BaZi JSON chart or equivalent verified four-pillar data as an evidence-linked static natal report. Use when a calculator hands off its artifact or someone asks to 解读八字, 看命局, explain day-master strength, structure, or favorable elements from an existing chart. Not for raw birth details, relationship matching, luck cycles, dated predictions, or incomplete source data.
license: MIT
metadata:
  version: "0.8.2"
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

Assign stable raw evidence ids before writing prose:

- Collect `[P-year]`, `[P-month]`, `[P-day]`, and `[P-hour]` for primary pillars.
- Collect `[B-year]`, `[B-month]`, `[B-day]`, and `[B-hour]` for boundary and time basis.
- Preserve structural interaction ids such as `[interaction-001]`, scoring ids such as `[base.visible.month]` and `[adjust.seasonal.木]`, and strength component names.
- Prefix alternate evidence with `[ALT-...]`; prefix Shen Sha with `[SS-...]` and label it secondary.

Then assign sequential compact markers `〔1〕`, `〔2〕`, and so on to the evidence used in reader prose. Cite every substantive reader-layer sentence with one or more compact markers; do not expose raw ids there. In the final appendix, map each used marker to the exact raw id, exact source value, and evidence class. Deduplicate the appendix: one raw id, one source fact. If evidence conflicts, describe the tension instead of selecting the more flattering result.

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

Never average their pillars, percentages, strength scores, or interpretations. Lower the report's claim confidence where sensitivity is material. Cite reader-layer sensitivity statements with compact markers and retain primary and alternate raw evidence separately in the final appendix.

## Required report order

Write the whole report in the user's language and render the matching localized headings in `references/output-template.md`. Keep exactly these seven sections:

1. Conclusion at a glance
2. Chart overview
3. Element and day-master summary
4. Core structure
5. Strengths and tensions
6. Relationship, work, and reflection prompts
7. Technical basis and evidence

Make sections 1–6 the reader layer. Put the conditional conclusion, material uncertainty, and scope disclaimer first. Show a concise four-pillar table in section 2. In section 3, display five-element percentages and day-master scores as whole numbers, and state that they are heuristic model outputs, not probabilities. Keep raw ids, full checksums, model ids, exact arithmetic, and unrounded values out of sections 1–6. Use compact markers only in those sections.

Make section 7 the final audit appendix. Include source status, full checksum when available, boundary rules, rule and scoring model ids, full unrounded values, component ledger, exact arithmetic, and separate alternate calculations. Map every marker used in the reader layer to its exact raw id and source value, and state whether it is primary, calculated heuristic, alternate, or secondary Shen Sha evidence.

## Write safely

Create UTF-8 Markdown only after validation and evidence indexing. Use the portable source name in `bazi_reading_<name>.md`; preserve the display name inside the report. Do not overwrite a different existing report. When a same-name file already exists, reuse it only if its recorded source checksum matches; otherwise append the first eight checksum characters.

Report the reading path and source JSON path. Do not create new chart JSON, alter the source artifact, or invoke the chart calculator after a valid hand-off.

See `references/examples.md` for a hand-off, alternate-boundary treatment, and corrupt-source refusal.
