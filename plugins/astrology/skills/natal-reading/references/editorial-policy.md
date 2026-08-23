# Natal reading editorial policy

Applies after `scripts/validate_natal.py` has accepted the source and the evidence ledger exists.

## Two-output boundary

Write a reader report and a separate evidence artifact. They serve different readers and must not be merged.

- The reader report is the default handoff, written in the user's language as a human-first interpretation. It may carry a compact model data card.
- The evidence artifact holds source status, the checksum, the backend actually used, exact degrees and orbs, raw ids, and every recorded limitation.
- Link to the evidence artifact once, as the final line of the reader report.

## Depth

A natal chart carries thirteen bodies, four angles, six lots and forty-odd aspects. Target **1,800–2,300 Chinese characters**, or comparable depth in another language — the band for a single-system natal reading with many positions.

A band is a target, not a cap. Overshooting by roughly a tenth while every paragraph carries evidence is not a defect. Undershooting usually is: it means a conclusion arrived without its countervailing condition or its observable.

Never delete a supported conclusion to reach a number, and never pad to reach one.

## What the reader report may not contain

- Raw evidence ids, checksums, backend identifiers, or ledger keys.
- Exact orbs to two decimals. Say "within half a degree" or "a wide square"; the exact figure lives in the evidence artifact.
- Any statement that a placement causes an outcome.
- Occupation, income, promotion, diagnosis, lifespan, fertility, gender, sexuality, or a verdict on character.

## Weighting

Orb is the whole difference between a claim worth making and one worth mentioning. A 0.5° square and a 7° square are not the same statement, and a report that treats them alike asserts more than the chart carries. Lead with the tightest aspects and say when something is wide.

A body at a critical degree — the first or last degree of a sign — changes sign on a small time error. Any conclusion resting on one is conditional on the birth minute being exact, and the report says so where the claim is made, not only in the data card.

## Schools

This plugin uses classical rulerships only. The modern assignments — Uranus to Aquarius, Neptune to Pisces, Pluto to Scorpio — are a live disagreement between traditions, and stating one as fact asserts a school rather than a position. Say this once, where dignities are first discussed.

The house system is recorded in the artifact and named in the data card. A different system moves placements between houses, and a reader deserves to know which one produced what they are reading.

## Limitations

An unavailable body is a gap in the calculation, never an absence in the person. A chart short five asteroids is not a chart without them, and a reading that quietly omits them presents a partial chart as a complete one. Name them.

If the artifact records an ephemeris fallback, say that positions came from the analytical backend rather than the Swiss data files, once, in the data card.

## Model data card

Late in the report, compact:

- ascendant with sign and degree, the sect light and its condition, the house system, the zodiac;
- no more than three further indicators;
- one sentence stating that this is a traditional interpretive model, not a measurement, and that classical rulerships were used.

End with one link to the evidence artifact.
