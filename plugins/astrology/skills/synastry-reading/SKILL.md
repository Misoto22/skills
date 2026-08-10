---
name: synastry-reading
description: Use when the synastry calculator hands off a completed two-person data file, or when someone supplies equivalent natal blocks, cross-chart aspects with orbs, and both house-overlay directions and asks for 解读, 分析, a relationship reading, significant dynamics, or what the pattern means. Not for calculating birth details, single natal charts, transits, forecasts, compatibility scores, or files missing required synastry sections.
license: MIT
metadata:
  version: "0.8.3"
argument-hint: "[synastry-data-file] [--out=source-directory]"
---

# Synastry Reading

Turn one completed two-person synastry data file into a structured Markdown reading whose claims remain traceable to the measurements that support them.

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
- relationship context explicitly supplied by the user, or `not stated`
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

Route evidence into relationship mechanisms before real-life applications. Use these associations as starting points, not as a mechanical lookup table:

| Core mechanism | Start with | Relevant overlays |
|---|---|---|
| Relationship signature | repeated personal/angle themes, Sun, Moon, Ascendant | 1st, 4th, 7th, 8th |
| Reciprocity and asymmetry | body ownership, parallel contacts, both overlay directions | compare every activated house by direction |
| Emotional bond and security | Moon, Venus, Saturn; Sun as support | 4th, 8th, 12th |
| Attraction, romance, and intimacy | Venus, Mars, Moon, Sun, Ascendant; Pluto as support | 5th, 7th, 8th |
| Communication and mental rhythm | Mercury, Moon, Jupiter, Saturn | 3rd, 9th, 11th |
| Conflict, power, and repair | Mars, Mercury, Moon, Saturn; Pluto and Uranus as support | 1st, 6th, 8th |
| Trust, boundaries, and commitment | Moon, Venus, Saturn; nodes as support | 4th, 7th, 8th, 12th |
| Growth, values, and shared direction | Sun, Jupiter, Saturn, Midheaven; nodes as support | 9th, 10th, 11th |

Compare what each person activates and receives before describing a shared effect. A reciprocal theme may be experienced differently; do not flatten both overlay directions into one claim.

## Select applied life domains

The fixed core describes how the relationship works. The `Applied life domains` section describes where those mechanisms matter in practice.

1. Include every domain the user explicitly requests.
2. For a requested domain with weak evidence, keep the domain and state that the source does not support a confident domain-specific reading. Do not fill the gap with generic sign descriptions.
3. Include an unrequested domain only when it has either:
   - two separate relevant Ptolemaic contacts, with at least one involving a personal body or angle; or
   - one tight personal-body or angle contact plus one directly relevant directional house overlay.
4. Omit every unsupported unrequested domain.

For this selection rule, `tight` means an orb of 1.00° or less and still within the source's declared orb. Do not widen the source's settings to make a domain qualify.

Common domains are:

| Applied domain | Start with | Relevant overlays |
|---|---|---|
| Friendship, community, and social networks | Sun, Moon, Mercury, Jupiter, Ascendant | 3rd, 9th, 11th |
| Daily life, home, family, and care | Moon, Mercury, Venus, Saturn, IC | 4th, 6th |
| Career, business, and creative collaboration | Sun, Mercury, Mars, Jupiter, Saturn, Midheaven | 5th, 6th, 10th, 11th |
| Money, shared resources, and risk tolerance | Venus, Jupiter, Saturn; Pluto as support | 2nd, 8th, 10th |

Add another requested or strongly activated domain under the same evidence rule. Do not infer that the people are lovers, friends, relatives, colleagues, housemates, or financial partners when the request does not state the relationship.

A measurement may inform more than one mechanism or domain when the explanation is genuinely different. Cross-reference the earlier mechanism and explain only its new practical implication instead of repeating the paragraph.

## Write from measurements, not verdicts

Every substantive paragraph must include an inline evidence parenthesis or point to an item in that section's evidence list. Cite:

- aspects as `<owner> <body> <aspect> <owner> <body>, orb <value>°`
- overlays as `<owner>'s <body> falls in <other owner>'s <ordinal> house`

Preserve every orb exactly. Separate what the file states from what the tradition associates with it:

- Measurement: `A Venus trine B Moon, orb 0.42°`.
- Interpretation: `This can describe affection and emotional response finding an easy rhythm.`

Use conditional language: `can`, `may`, `tends to`, `is often read as`. Do not state that a placement proves character, guarantees an outcome, predicts an event, or makes the relationship good or bad. Do not assign percentages, star ratings, or compatibility scores; the source provides no scale that could calculate one.

Practical guidance must follow from the pattern already described. Keep it specific enough to try, but do not present medical, legal, financial, or psychological conclusions as astrology.

## Write the structured Markdown report

Read [output-template.md](references/output-template.md) before writing. Use every fixed core heading in its given order. Under `Applied life domains`, include only requested domains and unrequested domains that pass the selection rule.

Keep a fixed core heading when evidence is weak. State the limit briefly, include the available evidence list, and omit unsupported advice. Each fixed core section and selected domain ends with a compact evidence list; add practical guidance only when it follows from cited patterns.

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
