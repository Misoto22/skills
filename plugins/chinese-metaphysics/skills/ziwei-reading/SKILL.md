---
name: ziwei-reading
description: Interpret an already-placed Zi Wei 命盘 artifact, or equivalent verified twelve-palace data, writing a reader report plus a separate audit artifact and, when asked, an ink-wash HTML poster. Use for 解读紫微, 看命盘, 看十二宫, or explaining the stars sitting in 命宫, the 生年四化, and what each 大限 window emphasizes. Not for unplaced birth records, 八字 four pillars, comparing two systems against each other, matching two people, 流年, or dated predictions.
license: MIT
metadata:
  version: "0.8.4"
---

# Zi Wei Reading

Read one complete chart and write `ziwei_reading_<name>.md` plus `ziwei_reading_evidence_<name>.md`. Interpret; never re-place. The first is a reader report; the second is a separate evidence artifact.

Before writing either file, read and follow `shared/report-presentation.md`. It defines the common localization, data-card, and separate-evidence boundary rules; this skill defines the Zi Wei evidence and section requirements.

## Route and source gate

- Raw name/place/date/time/gender belongs to `ziwei-chart` first.
- Four pillars, ten gods, or five-element strength belong to `bazi-reading`.
- A BaZi chart and a Zi Wei chart read against each other belong to `bazi-ziwei-cross`.
- Two-person matching belongs to `bazi-compatibility`.
- Annual and monthly transformations, 流年, dated events, and forecasts are outside this release.

Accept one of:

1. A `chinese-metaphysics.ziwei-chart` JSON artifact at schema version 1 with a valid canonical checksum.
2. Its verified Markdown rendering together with the matching JSON. Markdown alone is not a machine source.
3. Complete pasted equivalent data containing identity, the lunar date and hour branch, the year pillar and its polarity, the bureau, the life and body palaces, all twelve palaces with their stems and placed stars, the year transformations including any unplaced ones, twelve decade ranges, the model version, and alternate sensitivity. Mark this source `pasted-complete`; do not pretend it had a checksum.

Use the vendored `shared/bazi/artifacts.py` validator for a JSON artifact. Stop on checksum mismatch, unsupported schema or version, fewer than twelve palaces, a missing life or body palace, a transformation naming a star that appears nowhere, decade ranges running in two directions, or a sensitivity flag without a complete alternate. Name the exact defect and route raw details back to `ziwei-chart`; never patch or infer a field.

## Build an evidence ledger first

Assign stable raw evidence ids before writing prose:

- Collect `[G-命宫]` through `[G-父母]` for the twelve palaces, each carrying its branch, stem, and star list.
- Collect `[S-<star>]` for every placed star, with its palace, brightness, and transformation.
- Collect `[H-禄]`, `[H-权]`, `[H-科]`, `[H-忌]` for the year transformations, and `[H-unplaced]` for any this release does not place.
- Collect `[D-01]` through `[D-12]` for decade ranges, and `[B-bureau]`, `[B-lunar]`, `[B-year]` for the bureau, lunar date, and year pillar.
- Prefix alternate evidence with `[ALT-...]`.

Use this ledger to build the evidence artifact's heading-based claim map. Do not expose its ids in the reader report.

## Interpretation discipline

- Say "in this traditional model," "suggests," or "is commonly read as." Never present metaphysical interpretation as scientific fact, certainty, diagnosis, or fate.
- Start from the life palace, its stars and their brightness, the opposite palace, and the three-harmony palaces. A single star does not establish a pattern by itself.
- Treat the four transformations as the chart's emphasis, not its verdict. A 化忌 marks where attention concentrates and friction gathers, not a doomed palace.
- Read an empty palace through its opposite palace rather than declaring the matter absent.
- Keep brightness secondary to placement. A 庙 star in a palace the person never engages is not a conclusion.
- Say plainly that the recorded school is one lineage among several, and that another lineage would place some stars or transformations differently. `methodology.school_notes` names the specific divergences; do not hide them.
- Report an unplaced transformation as a gap in this release, never as an absent transformation.
- Do not apply gender-dependent conventions beyond the decade direction the source already recorded.
- Do not infer personality disorders, health conditions, fertility, lifespan, wealth amount, moral character, or inevitable relationship outcomes.
- Give practical actions as low-risk reflection prompts, not commands to make medical, legal, financial, employment, or relationship decisions.

## Decade ranges

Decade ranges are structural windows, not predictions. Describe what each window emphasizes by the palace it occupies; do not attach events, dates, or outcomes to it. Say once that the ranges are calculated positions, and that this release computes no annual or monthly layer on top of them.

## Alternate-chart sensitivity

When a 00:00-boundary alternate exists, interpret primary and alternate independently. The alternate shifts the lunar day, which moves 紫微 and every star anchored to it, so the two charts can disagree about the whole structure rather than one detail. Separate:

- stable findings supported by both charts;
- changed palace evidence and every conclusion it affects;
- claims that should be withheld because the boundary choice changes them.

Never average their palaces, star lists, or interpretations. Lower the report's claim confidence where sensitivity is material. Retain primary and alternate raw evidence separately in the evidence artifact.

## Required report order

Keep exactly these five reader-report sections, using the structure in `references/output-template.md`:

1. Life palace and main pattern
2. Palace emphases
3. Transformations, strengths, and tensions
4. Decade structure and reflection
5. Model data card

Put the conditional conclusion first, but lead with the person's lived pattern rather than source confidence or a method disclaimer. Develop the pattern, its countervailing tension, and its practical expression to the depth required by `shared/report-presentation.md`. Show a compact twelve-palace table only when it helps section 2. In section 5, state once that brightness and transformations are declared lineage conventions, not measurements.

Write the separate evidence artifact after the reader report. In addition to the shared evidence requirements, include source status, the lunar conversion and day boundary, the bureau derivation, the full palace ledger, the transformation ledger with unplaced entries, decade calculations, and separate alternate placements.

## Optional ink-wash poster

Offer a poster only when the person asks for a visual, shareable, or printable report. It never replaces the reader report or the evidence artifact.

Read `shared/divination-report/poster-contract.md`, write the payload as data only, and render it:

```bash
python3 shared/divination-report/render_poster.py --data POSTER_PAYLOAD.json --out ziwei_poster_NAME.html
```

Fill `meta.system_label` with 紫微斗数, put the bureau, life palace, and body palace in `core_metrics`, and use `axes` for the life-palace statement. Set `footer.evidence_link` to the evidence artifact filename. Never write the HTML yourself and never edit the template for one reading.

## Write safely

Create UTF-8 Markdown only after validation and evidence indexing. Use portable source names in `ziwei_reading_<name>.md` and `ziwei_reading_evidence_<name>.md`; preserve the display name inside both files. Do not overwrite a different report pair. When a same-name reader report or evidence artifact already exists, reuse the pair only if both record the same source checksum; otherwise append the first eight checksum characters to both names.

Report the reader-report path, evidence-artifact path, source JSON path, and the poster path when one was made. Do not create new chart JSON, alter the source artifact, or invoke the placer after a valid hand-off.

See `references/examples.md` for a hand-off, alternate-boundary treatment, and corrupt-source refusal.
