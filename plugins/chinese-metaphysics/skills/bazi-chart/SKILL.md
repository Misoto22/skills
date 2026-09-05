---
name: bazi-chart
description: Calculate one reusable BaZi chart from a named person's exact birth date, minute, and birthplace, write canonical JSON plus data-only Markdown, then start the natal reading automatically. Use for 八字排盘, 生辰八字, four pillars, or informal single-person birth details. Not for two-person compatibility, existing-chart interpretation, Da Yun, annual luck, or event forecasts.
license: MIT
metadata:
  version: "0.16.1"
---

# BaZi Chart

Calculate one static natal chart, write `bazi_<name>.json` and `bazi_<name>.md`, then hand the verified JSON to `bazi-reading` automatically. The artifacts contain calculation data only; never interpret the chart here.

## Route before calculating

- If the user supplied two people and wants to know whether they match, route to `bazi-compatibility`.
- If the user supplied an existing chart and wants meaning, route to `bazi-reading` without recalculating.
- If they ask for Da Yun, annual luck, event dates, or forecasts, state that this first release is natal-only and do not improvise those calculations.

## Require one resolved birth record

Collect these fields without guessing:

- `name`: display identity for the artifact.
- `birth_place`: unambiguous city/region/country.
- `birth_date`: exact `YYYY-MM-DD` in the declared calendar.
- `birth_time`: exact `HH:MM` in 24-hour form. Refuse an hour-only or approximate time.
- `calendar`: `gregorian` or `lunar`. A lunar date also requires explicit `leap_month: true|false`.
- `timezone`: historical IANA zone such as `Asia/Shanghai`.
- `latitude` and `longitude`: decimal degrees for the birthplace.
- `utc_offset_minutes` only when an authoritative historical source must override IANA data.
- `fold: 0|1` only to resolve a repeated DST wall time.
- `gender` is optional. Never infer it from a name, relationship, or pronoun.

Resolve a place through an available geocoder or map source. If multiple places match, stop for a location choice. Do not select the largest or most famous city silently. Preserve the user's stated place in `birth_place` and add the resolved coordinates and IANA zone to the request.

## Calculation contract

The shared calculator applies these declared rules:

1. Convert lunar input under GB/T 33661-2017 rules in Beijing civil time.
2. Resolve the historical civil instant through IANA data or the explicit offset.
3. Calculate equation of time and longitude correction separately, then derive true solar time.
4. Change the year at the exact 315° Li Chun instant and the month at each exact 12-`jie` boundary.
5. Use a 23:00 true-solar day boundary. For 23:00-23:59, also emit a 00:00-boundary alternate; never average the two.
6. Derive fixed structural facts from `bazi-chart-rules-v1` and numeric outputs from `bazi-score-v1`.

Five-element percentages and day-master strength are transparent heuristic-model outputs. They are not probabilities, measurements, or results endorsed by a calendar authority or ephemeris provider.

## Run the calculator

Work from this skill directory. Put the resolved object in a UTF-8 JSON file and run:

```bash
python3 scripts/compute_chart.py --request REQUEST.json --out OUTPUT_DIRECTORY --language zh
```

Inline JSON is also accepted:

```bash
python3 scripts/compute_chart.py --json '{...}' --out OUTPUT_DIRECTORY --language en
```

The runtime requires `pyswisseph`, declared in `requirements.txt`. If it reports the dependency missing, surface that exact installation error; do not replace astronomical boundaries with approximate dates. An optional Swiss data directory may be supplied with `--ephemeris-path`.

The command prints exactly two absolute paths on success: canonical JSON first, data-only Markdown second. Exit code 2 means no valid pair was created. Never create or repair one artifact manually after a calculation failure.

## Validate and hand off

Read the JSON back through the gate the reading skill runs:

```bash
python3 scripts/validate_artifact.py CHART.json
```

It checks the schema and version, the canonical checksum, all four primary pillars with their facts and scores, the time corrections and model ids, and a complete alternate whenever `alternate_day_boundary` is true. Exit 2 means the run produced something unreadable: report every defect it names, and never create or repair an artifact by hand.

Then confirm the Markdown names the same checksum and contains no interpretation.

After validation, automatically invoke `bazi-reading` with the exact JSON path. Do not wait for a second user request. Do not invoke it when calculation or validation failed. After the reading completes, report the chart JSON, chart Markdown, reader-report Markdown, and separate evidence-artifact Markdown paths.

## Privacy and limits

Birth details are sensitive personal data. Write only to the user-selected output directory, do not send them elsewhere, and do not add unrelated identity details. This skill calculates static natal structure only: no Da Yun, annual or monthly luck, event timing, medical or psychological diagnosis, deterministic claims, or compatibility verdicts.

See `references/request.example.json` for the request shape and `references/examples.md` for boundary and failure examples.
