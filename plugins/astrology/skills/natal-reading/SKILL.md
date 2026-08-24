---
name: natal-reading
description: Explain a natal chart artifact someone already has — what the rising sign shapes, where the sect light sits, which aspects are tight enough to lean on, and what the angles and lots add. Writes a reader report plus an auditable evidence file, and a shareable ink-wash page on request. Use for 解读星盘, 看本命盘, 我的上升是什么意思, or asking what a placement or aspect pattern means. Not for computing a chart from raw birth details, 合盘 between two people, transits, progressions, returns, or predicting a dated event.
license: AGPL-3.0-or-later
metadata:
  version: "0.9.2"
---

# Natal Reading

Read one complete natal artifact and write `natal_reading_<name>.md` plus `natal_reading_evidence_<name>.md`. Interpret; never recalculate. The first is a reader report; the second is a separate evidence artifact.

Before writing either file, read and follow `references/editorial-policy.md`. It defines the localization, data-card, and separate-evidence boundary rules this plugin's readings share.

## Route and source gate

- Raw birth details belong to `natal-chart` first.
- Two people belong to `synastry` and then `synastry-reading`.
- Transits, progressions, returns, dated events, and forecasts are outside this release.

Accept one of:

1. An `astrology.natal-chart` JSON artifact at schema version 1 with a valid canonical checksum.
2. Its verified Markdown rendering together with the matching JSON. Markdown alone is not a machine source.

Validate with the vendored `scripts/validate_natal.py`. Stop on checksum mismatch, unsupported schema or version, missing house cusps, a position without a house, an aspect naming a body that appears nowhere, or partial lots. Name the exact defect and route raw details back to `natal-chart`; never patch or infer a field.

## Build an evidence ledger first

Assign stable raw evidence ids before writing prose:

- `[B-<body>]` for every position, carrying sign, degree, house, retrograde state, dignities and critical-degree flag.
- `[A-<angle>]` for each of the four angles and the derived points.
- `[X-<left>-<kind>-<right>]` for each aspect, with its exact orb.
- `[L-<lot>]` for each lot, and `[S-sect]` for the sect and its basis.
- `[LIM-<code>]` for every recorded limitation.

Use this ledger to build the evidence artifact's heading-based claim map. Do not expose its ids in the reader report.

## Interpretation discipline

- Say "in this tradition," "is commonly read as," or "suggests." Never present astrological interpretation as scientific fact, certainty, diagnosis, or fate.
- Start from the ascendant, its ruler, the sect light, and the tightest aspects. A single placement does not establish a pattern.
- Weight an aspect by its orb. A 7° square is not the same claim as a 0.5° one, and a report that treats them alike is asserting more than the chart carries.
- Treat a critical-degree placement as explicitly fragile: a body in the first or last degree of a sign changes sign on a small time error, so any conclusion resting on it is conditional on the birth minute being exact.
- Report retrograde as a recorded state, not a verdict on the person.
- Say that classical dignities are used and modern rulerships deliberately are not, once, where dignities are first discussed.
- Read a limitation as a gap in the calculation, never as an absence in the person. A chart short five asteroids is not a chart without them.
- Do not infer personality disorders, health conditions, fertility, lifespan, wealth amount, moral character, gender, sexuality, or inevitable relationship outcomes.
- Give practical actions as low-risk reflection prompts, not commands to make medical, legal, financial, employment, or relationship decisions.

## Required report order

Keep exactly these five reader-report sections, using the structure in `references/output-template.md`:

1. Ascendant and the chart's shape
2. The sect light and its condition
3. Tightest aspects, strengths and tensions
4. Angles, lots, and reflection
5. Model data card

Lead with the person's lived pattern rather than a method disclaimer. Develop the pattern, its countervailing tension, and its practical expression to the depth `references/editorial-policy.md` sets for a single-system natal reading with many positions — thirteen bodies, four angles, six lots and forty-odd aspects do not compress into a four-placement band.

Write the separate evidence artifact after the reader report. Include source status and checksum, the backend actually used, every position and aspect with exact orbs, sect and its basis, all lots, every limitation, and a claim map mirroring the reader report's five headings.

## Optional ink-wash poster

Offer a poster only when the person asks for a visual, shareable, or printable report. It never replaces the reader report or the evidence artifact.

Read `shared/divination-report/poster-contract.md`, write the payload as data only, and render it:

```bash
python3 shared/divination-report/render_poster.py --data POSTER_PAYLOAD.json --out natal_poster_NAME.html
```

Fill `meta.system_label` with the tradition and house system, put the ascendant, sect light and its condition in `core_metrics`, and use `distribution` for the element or modality balance with `value` carrying the true count. Put every recorded limitation in `conflicts.rows`; a poster that hides a missing body is a failed poster. Set `footer.evidence_link` to the evidence artifact filename. Never write the HTML yourself and never edit the template for one reading.

## Write safely

Create UTF-8 Markdown only after validation and evidence indexing. Use portable source names in `natal_reading_<name>.md` and `natal_reading_evidence_<name>.md`; preserve the display name inside both files. Do not overwrite a different report pair. When a same-name pair already exists, reuse it only if both record the same source checksum; otherwise append the first eight checksum characters to both names.

Report the reader-report path, evidence-artifact path, source JSON path, and the poster path when one was made. Do not create new chart JSON, alter the source artifact, or invoke the calculator after a valid hand-off.

See `references/examples.md` for a hand-off, a critical-degree treatment, and a corrupt-source refusal.
