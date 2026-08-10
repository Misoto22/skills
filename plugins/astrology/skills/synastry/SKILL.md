---
name: synastry
description: Compute a synastry data file for two people from their birth details — both natal charts, cross-chart aspects under separate Ptolemaic and minor orbs, and house overlays in both directions — then hand the completed file to the separate reading skill. Use when two sets of birth details arrive and the ask is 合盘, synastry, a compatibility or relationship chart, 星盘配对, 看看我俩的盘, or the details turn up informally as a name plus a date, a time, and a city. Not for one person's natal chart on its own, not for transits, horoscopes, or predictions, and not for reading back a chart file that already exists.
license: MIT
metadata:
  version: "0.8.2"
argument-hint: "[--language=en|zh] [--house-system=placidus]"
---

# Synastry

Turn two people's birth details into one plain-text data file: each natal chart, the aspects between them, and where each falls in the other's houses. After the file exists, hand it directly to `synastry-reading` for the separate Markdown interpretation.

The file is data. Element balance, modality balance, stellium calls, and anything resembling a verdict belong only in the reading file, written from the numbers rather than mixed into them. Keeping the two artifacts apart is what stops an inference being filed as a measurement.

## When this fires

- Two sets of birth details arrive together, however informally phrased.
- One set arrives and the other is already in the conversation.
- The ask names 合盘, synastry, a compatibility chart, 星盘配对, or a relationship chart.

It does not fire on a question about a chart file that already exists — answer that from the file. It does not fire on one person's natal chart alone, on transits, or on a forecast.

## The precondition, before anything else

**Both birth times must be given to the minute.** The Ascendant moves one degree every four minutes and a full sign roughly every two hours, so an hour-only time gives the wrong Ascendant, the wrong house cusps, and therefore the wrong half of the synastry.

If either time is missing or rounded to the hour, stop and say which person's time is needed. Do not substitute noon. Do not offer an early and a late variant. The script rejects the request for the same reason, so a workaround here only moves the failure later.

## Fields

Each person needs these. Anything else in the object is ignored.

| Field | Meaning | Example |
|---|---|---|
| `name` | What to call them in the report and the filename | `"Person A"` |
| `date` | Birth date, ISO | `"1990-03-14"` |
| `time` | Birth time, 24-hour, to the minute | `"07:42"` |
| `timezone` | IANA zone name for the birth place | `"Asia/Shanghai"` |
| `latitude` | Birth latitude, decimal degrees, north positive | `31.23` |
| `longitude` | Birth longitude, decimal degrees, east positive | `121.47` |
| `birth_place` | Shown in the header; not used in the arithmetic | `"Shanghai"` |
| `residence` | Shown in the header; not used in the arithmetic | `"Shanghai"` |
| `utc_offset_hours` | Optional override when the zone database is wrong for that date | `8.0` |

[references/request.example.json](references/request.example.json) is a complete request.

### Turning a place name into coordinates

Look the place up rather than recalling it, and state what you used. Two decimal places is enough: a 0.05° error moves the Ascendant by a few arc-minutes, which matters only for an aspect already inside half a degree.

Give the IANA zone name, not an offset. The script resolves the offset against the birth *date*, so a summer-time birth gets the offset in force that day — which is exactly the case a remembered constant gets wrong. Reach for `utc_offset_hours` only when the zone database is known to disagree with the local record for that date, and say why in the reply.

## Running it

```bash
python3 scripts/compute_synastry.py --request request.json --out .
```

| Flag | Default | Effect |
|---|---|---|
| `--request` | — | Path to the JSON request; `-` reads standard input |
| `--json` | — | The same JSON inline, instead of `--request` |
| `--out` | `.` | Directory to write into; created if absent |
| `--language` | `en` | `en` or `zh` for every label in the report |
| `--major-orb` | `8.0` | Orb for conjunction, opposition, trine, square, sextile |
| `--minor-orb` | `3.0` | Orb for the semi-sextile, semi-square, quintile, sesquiquadrate, biquintile, quincunx |
| `--house-system` | `placidus` | `placidus`, `koch`, `campanus`, `regiomontanus`, `equal`, `whole-sign` |
| `--ephemeris-path` | — | Directory of Swiss Ephemeris data files, when they are not on the default path |

The output lands at `<out>/synastry_<name-a>_<name-b>.txt`.

`pyswisseph` is the one dependency, and only the ephemeris backend touches it. If it is missing the script says so and exits; install it with `pip install pyswisseph` rather than falling back to an approximation.

## What the file contains

1. **Header** — engine, house system, and the reminder that the file is data.
2. **Each natal chart**, in the order given:
   - birth data as supplied, plus the resolved UTC offset
   - big three, then the ten planets with sign, degree, house, dignity, retrograde, and critical-degree flags
   - the four angles
   - Chiron, Ceres, Pallas, Juno, Vesta, Lilith, the mean nodes, Vertex, and East Point
   - the classical Lots, with the sect that chose the formulas
   - twelve house cusps and the bodies in each house
3. **Synastry** — every cross-chart aspect sorted tightest orb first, then house overlays in both directions.

## How it is computed

- **Ephemeris** — Swiss Ephemeris through `pyswisseph`; positions are geocentric ecliptic longitudes of date.
- **Houses** — Placidus by default, from the birth coordinates.
- **Nodes** — mean, not true. The true node stations and retrogrades, so charts drawn days apart disagree about a body neither person moved.
- **Dignities** — classical rulerships only. Modern assignments are a live disagreement between traditions, and a data file stating one as fact is asserting a school.
- **Lots** — classical formulas, with the Sun and Moon swapped for a nocturnal chart. Sect is decided by whether the Sun sits above the horizon.
- **Aspects** — computed over both charts in full, so an asteroid-to-asteroid contact is found on the same pass as a Sun-to-Moon one. The Descendant, Imum Coeli, and South Node are held out of that pass: each sits exactly opposite a body already included, and would report every contact twice under a second name.
- **Orbs** — two, not one. A single 8° orb lets the minor aspects outnumber the Ptolemaic ones and buries the pattern worth reading.

## Automatic reading hand-off

After writing the file:

1. Confirm that the raw data file exists and retain its exact path.
2. Invoke `synastry-reading` immediately with that path. Do not wait for another user request, and do not ask whether they also want an interpretation.
3. Keep the raw file untouched. Every interpretive sentence belongs in `synastry_reading_<name-a>_<name-b>.md`, never in the `.txt` file.
4. If calculation failed or no data file was written, do not invoke the reading skill.
5. If `synastry-reading` is unavailable, report the raw path and the missing reading component rather than improvising its job inline.

After the hand-off succeeds, name both output paths and give only the short overview returned by the reading skill. Repeat any coordinate, timezone, sign-boundary, or missing-ephemeris limitation that materially constrains the report.

Reply in the language the caller is writing in, and keep their register. The data file's labels are fixed by `--language`, so pass `zh` when the conversation is in Chinese rather than translating its contents in the reply. The reading skill follows that language into its separate Markdown report.

See [examples.md](references/examples.md) for three worked cases: a straight run with the reply it produced, a refusal on an hour-only birth time, and a Chinese-label run where the ephemeris was missing its asteroid file. Read it before the first run, and whenever a run has to report something it could not compute.

## Limits worth stating

1. **Coordinate precision sets the floor.** Two districts of one city differ by around 0.05°, a few arc-minutes on the Ascendant. Aspects inside 0.5° should be checked against a chart drawn from an exact birth location before anyone leans on them.
2. **Residence is metadata.** It appears in the header and enters no calculation; the chart is cast for the birth place.
3. **Chiron and the four asteroids need a separate ephemeris file.** They are read from the Swiss Ephemeris asteroid data, which a plain `pip install pyswisseph` does not carry. When it is absent those five bodies are dropped rather than the run failing, and the report names them under the points section — repeat that in the reply, because a missing body is easily read as a body with nothing to report. `--ephemeris-path` points at a directory holding the files.
4. **Nothing here is predictive.** The file states positions and angles. What they are taken to mean is a tradition, not a measurement, and the report is written so the difference stays visible.
