---
name: bazi-ziwei-cross
description: Read one person's finished 八字 artifact and finished 紫微 artifact against each other, recording every place the two systems agree, complement, or flatly contradict, without merging them into a single number. Use for 八字紫微综合, 双系统印证, 两盘合参, or asking whether the two systems say the same thing about one person. Not for placing either 命盘, reading one system by itself, matching two people, or forecasting.
license: MIT
metadata:
  version: "0.11.0"
---

# BaZi and Zi Wei Cross-Reading

Read two verified charts for **one person** against each other and write `cross_reading_<name>.md` plus `cross_reading_evidence_<name>.md`. Compare; never recalculate either source.

Before writing either file, read and follow `shared/report-presentation.md`. It defines the common localization, data-card, and separate-evidence boundary rules; this skill defines what counts as agreement and how a disagreement must be recorded.

## Route and source gate

- Raw birth details belong to `bazi-chart` and `ziwei-chart` first, in either order.
- One system alone belongs to `bazi-reading` or `ziwei-reading`.
- Two people belong to `bazi-compatibility`.
- Luck cycles, annual transformations, dated events, and forecasts are outside this release.

Require **both** of:

1. A `chinese-metaphysics.bazi-chart` JSON artifact at schema version 1 with a valid canonical checksum.
2. A `chinese-metaphysics.ziwei-chart` JSON artifact at schema version 1 with a valid canonical checksum.

Validate both with the vendored `shared/bazi/artifacts.py` validator. Stop and name the exact defect on any checksum mismatch, unsupported schema or version, or incomplete chart. Route raw details back to the placing skill; never patch, infer, or place a missing chart yourself.

### The two charts must describe the same person and the same moment

Before comparing anything, confirm that both artifacts carry the same `input.name`, `input.birth_date`, `input.birth_time`, `input.timezone`, and birthplace coordinates. If any differ, stop and say which field differs. Two charts for different moments produce a cross-reading that looks authoritative and means nothing.

## The year-pillar difference is expected, not an error

BaZi changes the year at the exact Li Chun instant; Zi Wei changes it at lunar new year. A person born between those two moments legitimately carries a different year stem in each system.

- Record the difference explicitly as a calendar-convention fact.
- Never adopt one system's year pillar for the other.
- Never treat it as a contradiction between the two readings.
- The Zi Wei year transformations follow the Zi Wei year stem, always.

Both charts also derive from the same true solar time, so a difference in day boundary sensitivity means both charts have an alternate. If only one does, say so; do not pair a primary with the other's alternate.

## Classify each comparison, then disclose it

For every domain you compare, record one of three verdicts and keep the class string the poster and evidence artifact both use:

| Verdict | Class | Means |
| --- | --- | --- |
| 同向 | `verdict-aligned` | Both systems point the same way from independent evidence |
| 互补 | `verdict-partial` | The systems describe different facets that do not contradict |
| 矛盾 | `verdict-conflict` | The systems point opposite ways on the same question |

Rules that keep this honest:

1. **Agreement must be independent.** Two conclusions that both trace back to the same birth hour are one piece of evidence, not two. Say so rather than counting it twice.
2. **A contradiction is recorded, never resolved by preference.** Do not pick the system you find more convincing, do not average them, and do not soften the language until the disagreement disappears.
3. **A contradiction lowers confidence.** Where the two systems oppose each other on a question, the honest output is a narrower claim, not a confident one.
4. **Never manufacture agreement.** A cross-reading whose value is "both systems agree on everything" is almost always a reading that stopped looking.
5. **Vocabulary does not transfer.** 用神 is not a palace, 化忌 is not an unfavourable element, and a 格局 is not a 主星 arrangement. Compare what each conclusion says about the person, not what the terms sound like.

## Build a paired evidence ledger first

Assign stable raw evidence ids before writing prose:

- Carry BaZi ids forward unchanged: `[P-*]`, `[B-*]`, `[interaction-*]`, `[base.*]`, `[adjust.*]`.
- Carry Zi Wei ids forward unchanged: `[G-*]`, `[S-*]`, `[H-*]`, `[D-*]`.
- Add `[X-<domain>]` for each cross comparison, naming the exact source ids on each side and the verdict.
- Add `[X-conflict-*]` for each recorded contradiction, with both positions and its impact.
- Prefix alternate evidence with `[ALT-...]` and keep each system's alternate separate.

Use this ledger to build the evidence artifact's heading-based claim map. Do not expose its ids in the reader report.

## Interpretation discipline

Everything the single-system reading skills forbid still applies here. In addition:

- Say plainly that these are two traditional models, each with its own lineage conventions, being compared — not two independent measurements converging on a truth.
- Do not present cross-system agreement as validation, proof, or increased accuracy.
- Do not produce a combined score. There is no defensible arithmetic that merges a five-element distribution with a palace arrangement, and inventing one would look more rigorous than it is.
- Confidence is qualitative and per-domain: state what the agreement or disagreement does to that specific claim.
- Do not infer personality disorders, health conditions, fertility, lifespan, wealth amount, moral character, or inevitable relationship outcomes.
- Give practical actions as low-risk reflection prompts, not commands to make medical, legal, financial, employment, or relationship decisions.

## Required report order

Keep exactly these five reader-report sections, using the structure in `references/output-template.md`:

1. What both charts describe
2. Where they agree
3. Where they diverge
4. What the divergence means for reading this
5. Model data card

Lead with the person's lived pattern rather than a method disclaimer. Develop the central pattern, the main tension, and each system's distinct contribution to the depth `shared/report-presentation.md` sets for a cross-system reading; the disclosure section is part of that length, not an overrun of it. Section 3 is not optional; when the two charts genuinely agree everywhere, say what you checked that could have disagreed and did not.

Write the separate evidence artifact after the reader report. Mirror the reader report's five headings in a claim map, one section each, so every paragraph can be traced to the ids on both sides that support it — a single combined ledger reads as complete and is not. In addition to the shared evidence requirements, include both source checksums, both model versions, the calendar-convention difference, the full cross ledger with every verdict and its supporting ids on both sides, and each system's alternates kept apart.

## Optional ink-wash poster

A cross-reading is what the poster was shaped for: the domain table and the disclosure table both come from this ledger. Offer it only when the person asks for a visual, shareable, or printable report; it never replaces the reader report or the evidence artifact.

Read `shared/divination-report/poster-contract.md`, write the payload as data only, and render it:

```bash
python3 shared/divination-report/render_poster.py --data POSTER_PAYLOAD.json --out cross_poster_NAME.html
```

Map the ledger straight through:

- `axes` — one statement per system, using each system's own vocabulary.
- `consistency` — the overall verdict and its class, from the table above.
- `domains.rows` — one row per compared domain, with a `readings` entry per system.
- `conflicts.rows` — **every** recorded contradiction. A poster that drops the disclosure table is a failed poster.
- `confidence.items` — one entry per system plus one for the cross-agreement.
- `footer.evidence_link` — the evidence artifact filename.

Never write the HTML yourself and never edit the template for one reading.

## Write safely

Create UTF-8 Markdown only after validating both sources and indexing the ledger. Use portable source names in `cross_reading_<name>.md` and `cross_reading_evidence_<name>.md`; preserve the display name inside both files. Do not overwrite a different report pair. When a same-name pair already exists, reuse it only if both files record the same two source checksums; otherwise append the first eight characters of the BaZi checksum to both names.

Report the reader-report path, evidence-artifact path, both source JSON paths, and the poster path when one was made. Do not create or alter either source artifact, and do not invoke a calculator after a valid hand-off.

See `references/examples.md` for a mismatched-source refusal, a recorded contradiction, and the calendar-convention difference.
