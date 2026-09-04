---
name: ziwei-chart
description: Place one twelve-palace Zi Wei Dou Shu 命盘 from someone's stated birth moment, birthplace, and gender, recording palaces, stars, 生年四化, and 大限 windows as reusable placement data. Use for 紫微斗数, 紫微排盘, 排紫微, 紫微命盘, 十二宫, or purple star astrology. Not for 八字 four pillars, matching two people, comparing two systems against each other, 流年 or monthly transformations, or a 命盘 that has already been placed.
license: MIT
metadata:
  version: "0.15.0"
---

# Zi Wei Chart

Calculate one static twelve-palace chart, write `ziwei_<name>.json` and `ziwei_<name>.md`, then hand the verified JSON to `ziwei-reading` automatically. The artifacts contain placement data only; never interpret the chart here.

## Route before calculating

- Four pillars, ten gods, or five-element strength belong to `bazi-chart`.
- Two people being matched belong to `bazi-compatibility`.
- An existing Zi Wei chart that needs meaning belongs to `ziwei-reading` without recalculating.
- A BaZi chart and a Zi Wei chart that both already exist, and need to be read against each other, belong to `bazi-ziwei-cross`.
- Annual or monthly transformations, 流年, dated events, and forecasts are outside this release; state that rather than improvising them.

## Require one resolved birth record

Collect these fields without guessing:

- `name`: display identity for the artifact.
- `birth_place`: unambiguous city/region/country.
- `birth_date`: exact `YYYY-MM-DD` in the declared calendar.
- `birth_time`: exact `HH:MM` in 24-hour form. Refuse an hour-only or approximate time; the hour branch moves both the life palace and the body palace.
- `calendar`: `gregorian` or `lunar`. A lunar date also requires explicit `leap_month: true|false`.
- `timezone`: historical IANA zone such as `Asia/Shanghai`.
- `latitude` and `longitude`: decimal degrees for the birthplace.
- `gender`: **required** and either `male` or `female`. Decade cycles run forward or backward by the year's polarity combined with gender, so the direction cannot be derived without it. Ask the person; never infer it from a name, relationship, or pronoun. If they decline, say the decade ranges cannot be calculated and stop.
- `utc_offset_minutes` only when an authoritative historical source must override IANA data.
- `fold: 0|1` only to resolve a repeated DST wall time.

Resolve a place through an available geocoder or map source. If multiple places match, stop for a location choice. Do not select the largest or most famous city silently.

## Calculation contract

The shared placer applies these declared rules:

1. Resolve the historical civil instant through IANA data or the explicit offset, then derive true solar time exactly as this plugin's BaZi charts do.
2. Convert the resolved date to a standardized Chinese lunar date under GB/T 33661-2017. Zi Wei places every star from the lunar month and day, not from solar terms.
3. Take the year pillar from the lunar year. **This is not the BaZi year pillar.** BaZi changes the year at Li Chun; Zi Wei changes it at lunar new year, so a January or early-February birth legitimately carries a different year stem in the two systems. Never reconcile that difference silently.
4. Place the life palace by counting months forward from 寅 and hours backward; place the body palace by counting hours forward instead.
5. Derive the bureau from the sexagenary sound of the life palace, then place 紫微 from the bureau and lunar day, and 天府 mirrored across the 寅-申 axis.
6. Use a 23:00 day boundary. For 23:00-23:59, also emit a 00:00-boundary alternate; the lunar day differs, which moves 紫微 and every star anchored to it. Never average the two.
7. Derive placements and the year transformations from `ziwei-chart-rules-v1`.

Star brightness and the transformation set are declared lineage conventions, not measurements. The rules file records the school and the readings this release does not follow.

## Run the placer

Work from this skill directory. Put the resolved object in a UTF-8 JSON file and run:

```bash
python3 scripts/compute_ziwei.py --request REQUEST.json --out OUTPUT_DIRECTORY --language zh
```

Inline JSON is also accepted:

```bash
python3 scripts/compute_ziwei.py --json '{...}' --out OUTPUT_DIRECTORY --language en
```

The runtime requires `pyswisseph`, declared in `requirements.txt`. If it reports the dependency missing, surface that exact installation error; do not replace the lunar conversion with an approximate date table. An optional Swiss data directory may be supplied with `--ephemeris-path`.

The command prints exactly two absolute paths on success: canonical JSON first, data-only Markdown second. Exit code 2 means no valid pair was created. Never create or repair one artifact manually after a placement failure.

## Validate and hand off

Read the JSON back through the gate the reading skill runs:

```bash
python3 scripts/validate_artifact.py CHART.json
```

It checks the schema and version, the canonical checksum, twelve palaces each carrying a branch, stem and name, the life and body palaces both marked and agreeing with their pointers, the bureau and lunar date and year pillar, every placed transformation landing on a star that sits in a palace, any unplaced transformation listed rather than dropped, twelve decade ranges running one direction, and a complete alternate whenever `alternate_day_boundary` is true. Exit 2 means the run produced something unreadable: report every defect it names, and never create or repair an artifact by hand.

Then confirm the Markdown names the same checksum and contains no interpretation.

After validation, automatically invoke `ziwei-reading` with the exact JSON path. Do not wait for a second user request. Do not invoke it when placement or validation failed. After the reading completes, report the chart JSON, chart Markdown, reader-report Markdown, and separate evidence-artifact Markdown paths.

## Privacy and limits

Birth details are sensitive personal data. Write only to the user-selected output directory, do not send them elsewhere, and do not add unrelated identity details. This skill places static natal structure and decade ranges only: no annual or monthly transformation, no 流年, no self-transformation, no event timing, no medical or psychological diagnosis, no deterministic claims, and no compatibility verdicts.

See `references/request.example.json` for the request shape and `references/examples.md` for boundary and failure examples.
