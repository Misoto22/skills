---
name: natal-chart
description: Compute one person's natal chart from an exact birth date, minute, and place: planet positions with sign, house, dignity and retrograde state, the four angles, intra-chart aspects, sect, and the classical lots, written as canonical JSON plus data-only Markdown. Use for 本命盘, 星盘, 出生星图, natal chart, birth chart, my rising sign, my chart's aspects, or where a planet sits. Not for two-person 合盘, interpreting a chart that already exists, transits, progressions, returns, or any dated prediction.
license: AGPL-3.0-or-later
metadata:
  version: "0.8.4"
---

# Natal Chart

Compute one static natal chart, write `natal_<name>.json` and `natal_<name>.md`, then hand the verified JSON to `natal-reading` automatically. The artifacts hold placement data only; never interpret the chart here.

## Route before calculating

- Two people being compared belong to `synastry`.
- An existing natal artifact that needs meaning belongs to `natal-reading` without recalculating.
- Four pillars or twelve palaces belong to the `chinese-metaphysics` plugin.
- Transits, progressions, solar and lunar returns, dated events, and forecasts are outside this release; state that rather than improvising them.

## Require one resolved birth record

A natal chart needs an exact time. Houses, the four angles, and the sect all move with it, and a chart missing them is not a shorter natal chart — it is a different artifact. Collect without guessing:

- `name`: display identity for the artifact, and nothing else.
- `birth.date`: exact `YYYY-MM-DD`.
- `birth.time`: exact `HH:MM` in 24-hour form, with `time_mode` set to `exact` and `time_accuracy_minutes` set to `0`.
- `birth.timezone`: historical IANA zone such as `Asia/Shanghai`.
- `birth.latitude` and `birth.longitude`: decimal degrees for the birthplace.

Resolve a place through an available geocoder or map source. If several places match, stop for a location choice; do not silently take the largest.

If the person only knows the hour, or only the date, say plainly that this skill cannot place houses or angles from it, and stop. Do not fall back to noon, and do not produce a chart with the angles quietly omitted.

## Calculation contract

The shared astronomy applies these declared rules:

1. Resolve the stated wall time through IANA historical data to one UTC instant.
2. Take apparent geocentric positions from Swiss Ephemeris. When its data files are unavailable, the run is refused unless `ephemeris_policy` is explicitly set to `allow-moshier`, and the fallback is then recorded as a limitation in the artifact.
3. Place houses under the requested system, `whole-sign` by default.
4. Derive sign, degree, house, retrograde state and classical dignities per body. Modern rulerships are deliberately absent: assigning Uranus to Aquarius is a live disagreement between traditions, and stating one as fact asserts a school rather than a position.
5. Find intra-chart aspects with the declared orbs, each pair recorded once.
6. Derive sect from the Sun's house, then the classical lots with the diurnal or nocturnal formula that sect selects.
7. Record every unavailable body as a limitation. A chart that is short five asteroids must say so rather than look complete.

## Run the calculator

Work from this skill directory. Put the resolved object in a UTF-8 JSON file and run:

```bash
python3 scripts/compute_natal.py --request REQUEST.json --out OUTPUT_DIRECTORY
```

Inline JSON is also accepted with `--json`. Swiss Ephemeris data files may be supplied with `--ephemeris-path`.

The runtime requires `pyswisseph`, declared in `requirements.txt`. If it reports the dependency missing, surface that exact installation error; do not substitute an approximate position table.

The command prints exactly two absolute paths on success: canonical JSON first, data-only Markdown second. Exit code 2 means no valid pair was created. Never create or repair one artifact manually after a calculation failure.

## Validate and hand off

Read the JSON back and verify:

- schema is `astrology.natal-chart`, version 1;
- checksum matches canonical content;
- twelve house cusps and at least the ascendant and midheaven exist;
- every position carries a sign, a house, a retrograde state and a critical-degree flag;
- each aspect pair appears once, and no body aspects itself;
- sect is stated with its basis;
- lots are either complete or absent, never partial;
- every unavailable body appears in `limitations`;
- Markdown names the same checksum and contains no interpretation.

After validation, automatically invoke `natal-reading` with the exact JSON path. Do not wait for a second user request, and do not invoke it when calculation or validation failed.

## Privacy and limits

Birth details are sensitive personal data. Write only to the user-selected output directory, do not send them elsewhere, and do not add unrelated identity details. The artifact keeps the resolved instant and the derived chart, not the supplied street address or place label.

This skill computes static natal structure only: no transits, no progressions, no returns, no event timing, no medical or psychological diagnosis, no deterministic claims, and no compatibility verdicts.

See `references/request.example.json` for the request shape and `references/examples.md` for boundary and failure cases.
