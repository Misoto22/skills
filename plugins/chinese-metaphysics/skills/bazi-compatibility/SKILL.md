---
name: bazi-compatibility
description: Compare two people from reusable BaZi chart JSON files, two complete birth records, or one of each; write auditable interaction data and transparent general or relationship-specific scores before automatic interpretation. Use for 八字合婚, 合八字, two-person compatibility, 配不配, or whether two charts work together. Not for one-person natal work, reading an existing comparison, forecasting, or missing birth minutes.
license: MIT
metadata:
  version: "0.9.1"
---

# BaZi Compatibility

Compare two validated sources, write `bazi_compatibility_<name-a>_<name-b>.json` plus data-only Markdown, then invoke `bazi-compatibility-reading` automatically.

## Route first

- One raw birth record belongs to `bazi-chart`.
- One existing chart needing meaning belongs to `bazi-reading`.
- An existing compatibility artifact needing meaning belongs to `bazi-compatibility-reading`.
- Luck cycles, dated predictions, and event timing are outside this release.

## Accepted source combinations

Accept chart + chart, raw birth + raw birth, or chart + raw birth. Prefer reusable chart JSON when available; never recalculate a valid existing chart.

A chart source must be schema `chinese-metaphysics.bazi-chart`, version 1, with a valid checksum and complete primary facts and score ledgers. If it declares a boundary alternate, that alternate must also be complete.

A raw source has the same exact requirements as `bazi-chart`: name, unambiguous place, exact date and minute, declared Gregorian or lunar calendar, IANA zone, latitude, longitude, and an explicit leap-month flag for lunar input. Resolve ambiguous places before running. Never infer a minute, place, leap month, gender, DST fold, or historical offset.

Birth data and chart artifacts are sensitive. Keep them in the user-selected output directory and do not transmit them elsewhere.

## Relationship context

Default to a relationship-neutral general comparison. Set a context only when the user states one clearly:

- `romance`: dating or romantic connection;
- `marriage`: spouses, marriage, or explicit 合婚;
- `friendship`: friends;
- `family`: relatives or household family dynamics;
- `work`: colleagues, founders, manager/report, or business collaboration.

Do not infer romance from two names, genders, or a vague “do we match?” request. An explicit context adds a separate contextual index; it never replaces or changes the general score.

## Numeric model contract

`bazi-compatibility-v1` always calculates five general dimensions with exact weights:

| Dimension | Weight |
|---|---:|
| Element complementarity | 25% |
| Directional day-master support | 20% |
| Cross-chart stem/branch interactions | 20% |
| Day-pillar core | 20% |
| Structural stability | 15% |

Every dimension carries positive and negative ledger entries. Preserve ownership for directional support: “A supplies B” is not interchangeable with “B supplies A.” Swapping left and right must preserve all numeric scores while reversing directional owners.

If either chart has a day-boundary alternate, compare all primary/alternate combinations and report the range. The displayed general score remains primary-primary. Do not average alternates or choose the most favorable pairing. Shen Sha is excluded from numeric scores and remains secondary evidence.

All percentages and 0-100 indexes are versioned heuristic outputs, not probabilities or guarantees of relationship success.

## Run the calculator

From this skill directory, create the request shape shown in `references/request.example.json` and run:

```bash
python3 scripts/compute_compatibility.py --request REQUEST.json --out OUTPUT_DIRECTORY
```

Inline JSON is accepted with `--json`. A stated context may be in `relationship_type` or supplied with `--relationship-type`. Raw inputs require `pyswisseph`, declared in `requirements.txt`; chart + chart does not recalculate astronomy. An optional Swiss data directory may be supplied with `--ephemeris-path`.

The command prints canonical JSON and data-only Markdown absolute paths, in that order. Exit code 2 means no valid artifact pair was created. Do not manually complete a partial comparison.

## Validate and hand off

Read the output JSON back and verify schema/version, checksum, both source identities and chart checksums, all five dimensions and weights, both directions where relevant, general arithmetic, optional contextual profile, confidence, and sensitivity variants. Confirm the Markdown names the same checksum and contains data only.

After validation, automatically invoke `bazi-compatibility-reading` with the exact JSON path. Do not wait for another user message and do not invoke it after any failure. After the reading completes, report both compatibility artifact paths, the reader-report path, and the separate evidence-artifact path.

This skill calculates evidence only. It must not issue a “soulmate,” “destined,” safe/unsafe, marry/divorce, hire/fire, medical, financial, legal, or deterministic verdict.
