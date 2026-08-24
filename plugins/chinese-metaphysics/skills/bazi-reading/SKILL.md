---
name: bazi-reading
description: Interpret a completed single-person BaZi JSON chart or equivalent verified four-pillar data as an evidence-linked static natal report. Use when a calculator hands off its artifact or someone asks to 解读八字, 看命局, explain day-master strength, structure, or favorable elements from an existing chart. Not for raw birth details, relationship matching, luck cycles, dated predictions, or incomplete source data.
license: MIT
metadata:
  version: "0.9.0"
---

# BaZi Reading

Read one complete chart and write `bazi_reading_<name>.md` plus `bazi_reading_evidence_<name>.md`. Interpret; never recalculate. The first is a reader report; the second is a separate evidence artifact.

Before writing either file, read and follow `shared/report-presentation.md`. It defines the common localization, data-card, and separate-evidence boundary rules; this skill defines the natal evidence and section requirements.

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

Use this ledger to build the evidence artifact's heading-based claim map. Do not expose its ids in the reader report.

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

Never average their pillars, percentages, strength scores, or interpretations. Lower the report's claim confidence where sensitivity is material. Retain primary and alternate raw evidence separately in the evidence artifact.

## Required report order

Keep exactly these five reader-report sections, using the structure in `references/output-template.md`:

1. Main pattern
2. Chart tendencies
3. Strengths and tensions
4. Relationships, work, and reflection
5. Model data card

Put the conditional conclusion first, but lead with the person's lived pattern rather than source confidence or a method disclaimer. Develop the pattern, its countervailing tension, and its practical expression to the depth required by `shared/report-presentation.md`; do not reduce the reader report to a score summary. Show a concise four-pillar table only when it helps section 2. In section 5, state once that five-element percentages and day-master scores are heuristic model references, not probabilities.

Write the separate evidence artifact after the reader report. In addition to the shared evidence requirements, include source status, boundary rules, rule and scoring details, the component ledger, and separate alternate calculations. Classify natal evidence as primary, calculated heuristic, alternate, or secondary Shen Sha evidence.

## Optional ink-wash poster

Offer a poster only when the person asks for a visual, shareable, or printable report. It never replaces the reader report or the evidence artifact.

Read `shared/divination-report/poster-contract.md`, write the payload as data only, and render it:

```bash
python3 shared/divination-report/render_poster.py --data POSTER_PAYLOAD.json --out bazi_poster_NAME.html
```

Fill `meta.system_label` with 八字, put the day master, month command, and structure in `core_metrics`, and use `distribution` for the five-element percentages with `value` carrying the true figure. When an alternate exists, say so in `confidence.note` rather than quietly posting the primary alone. Set `footer.evidence_link` to the evidence artifact filename. Never write the HTML yourself and never edit the template for one reading.

## Write safely

Create UTF-8 Markdown only after validation and evidence indexing. Use portable source names in `bazi_reading_<name>.md` and `bazi_reading_evidence_<name>.md`; preserve the display name inside both files. Do not overwrite a different report pair. When a same-name reader report or evidence artifact already exists, reuse the pair only if both record the same source checksum; otherwise append the first eight checksum characters to both names.

Report the reader-report path, evidence-artifact path, and source JSON path. Do not create new chart JSON, alter the source artifact, or invoke the chart calculator after a valid hand-off.

See `references/examples.md` for a hand-off, alternate-boundary treatment, and corrupt-source refusal.
