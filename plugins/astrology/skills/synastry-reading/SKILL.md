---
name: synastry-reading
description: Interpret an existing two-person synastry data file as an evidence-linked Markdown reading across love, friendship, business partnership, and money. Use after the synastry calculator hands off a completed file, or when someone supplies equivalent natal blocks, cross-chart aspects with orbs, and both house-overlay directions and asks for 解读, 分析, a reading, or what the relationship pattern means. Not for calculating from birth details, single natal charts, transits, forecasts, compatibility scores, or files missing required synastry sections.
license: MIT
metadata:
  version: "0.8.1"
argument-hint: "[synastry-data-file] [--out=source-directory]"
---

# Synastry Reading

Turn one completed two-person synastry data file into a fixed Markdown reading whose claims remain traceable to the measurements that support them.

This skill is the interpretation layer. It does not calculate a chart and it never changes the source file.

## When this fires

- The `synastry` skill has just written a data file and hands its exact path over.
- Someone supplies a `synastry_*.txt` file and asks what it means.
- Complete equivalent data is pasted: two natal blocks, cross-chart aspects with orbs, and house overlays in both directions.
- The request asks for 合盘解读, 合盘分析, relationship patterns, compatibility themes, or a reading of an existing result.

It does not fire on raw birth details; those belong to `synastry`. It does not fire on one natal chart, transits, horoscopes, forecasts, or a request to change the house system or orbs.

## Validate the source before interpreting

Read the whole source. A complete input has all four of these:

1. One natal block for each named person.
2. A cross-chart aspect table that names both bodies, the aspect, and the orb.
3. The first person's bodies falling in the second person's houses.
4. The second person's bodies falling in the first person's houses.

If any required part is absent, stop and name it. Do not write a partial report. Ask for the complete file or a new calculation; astrology knowledge is not a substitute for a missing measurement.

Optional bodies are different. When the source explicitly says an asteroid or point was not resolved, continue with the complete core data, repeat that limitation in the report, and make no claim that depends on the missing body.

If duplicated entries disagree, quote both conflicting measurements and stop. Do not choose whichever one makes a cleaner reading.

## Build an evidence ledger

Before drafting prose, extract a compact ledger containing:

- both names and the source language
- calculation engine, house system, and orbs in force
- stated coordinate, birth-time, timezone, and ephemeris limitations
- every cross-chart aspect exactly as written
- every house overlay in both directions

Keep body ownership explicit. `A Venus trine B Moon, 0.42°` and `B Venus trine A Moon, 0.42°` are not interchangeable. For overlays, record the source body, its owner, the house number, and whose houses receive it.

## Weight the evidence

Use this order to decide which measurements carry the reading:

1. Tight Ptolemaic aspects involving the Sun, Moon, Mercury, Venus, Mars, Ascendant, or Midheaven.
2. A theme repeated across two or more major aspects.
3. House overlays relevant to the dimension, checked in both directions.
4. Jupiter, Saturn, the outer planets, nodes, asteroids, lots, and minor aspects as supporting evidence.

No single minor aspect, asteroid, lot, or outer-planet contact carries a strong conclusion by itself. An exact contact is more prominent than a wide one, but the source's declared orbs remain unchanged.

Use the traditional topic associations as routing aids, not as a mechanical lookup table:

| Dimension | Start with | Relevant overlays |
|---|---|---|
| Love | Moon, Venus, Mars, Sun, Ascendant | 5th, 7th, 8th |
| Friendship | Sun, Moon, Mercury, Jupiter, Ascendant | 3rd, 9th, 11th |
| Business partnership | Sun, Mercury, Mars, Jupiter, Saturn, Midheaven | 6th, 10th, 11th |
| Money | Venus, Jupiter, Saturn, Pluto when present | 2nd, 8th, 10th |

A measurement may inform more than one dimension when the explanation is genuinely different. Do not repeat the same paragraph four times.

## Write from measurements, not verdicts

Every substantive paragraph must include an inline evidence parenthesis or point to an item in that section's evidence list. Cite:

- aspects as `<owner> <body> <aspect> <owner> <body>, orb <value>°`
- overlays as `<owner>'s <body> falls in <other owner>'s <ordinal> house`

Preserve every orb exactly. Separate what the file states from what the tradition associates with it:

- Measurement: `A Venus trine B Moon, orb 0.42°`.
- Interpretation: `This can describe affection and emotional response finding an easy rhythm.`

Use conditional language: `can`, `may`, `tends to`, `is often read as`. Do not state that a placement proves character, guarantees an outcome, predicts an event, or makes the relationship good or bad. Do not assign percentages, star ratings, or compatibility scores; the source provides no scale that could calculate one.

Practical guidance must follow from the pattern already described. Keep it specific enough to try, but do not present medical, legal, financial, or psychological conclusions as astrology.

## Write the fixed Markdown report

Read [output-template.md](references/output-template.md) before writing. Use every heading in its given order and do not merge the four relationship dimensions.

Choose the language this way:

1. Follow an explicit language request.
2. Otherwise use the source labels when they are consistently English or Chinese.
3. Otherwise use the language of the current conversation.

For a source file named `synastry_<names>.txt`, write `synastry_reading_<names>.md` beside it. If complete data was pasted, write the same filename pattern in the current output directory. Honor a caller's explicit output directory, but do not overwrite the source.

The evidence index at the end is deduplicated. Each entry contains the exact measurement and the report sections that used it. Limitations belong near the top and appear again beside any section they materially constrain.

## Report back

After the Markdown file exists:

1. Name the source path and the reading path.
2. Give a neutral two- or three-sentence overview drawn from the report.
3. Repeat any limitation that removes a commonly read body or makes an angle or overlay uncertain.
4. Stop. The complete reading is in the file; do not paste it all into the chat unless asked.

Read [examples.md](references/examples.md) before the first run and whenever the input is incomplete or the ephemeris coverage is degraded.
