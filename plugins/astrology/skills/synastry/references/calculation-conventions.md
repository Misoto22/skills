# Calculation conventions

These are versioned plugin conventions, not universal astrology rules or scientifically validated compatibility scales.

## Contents

1. [Profiles](#profiles)
2. [Raw measurements and derived conventions](#raw-measurements-and-derived-conventions)
3. [Time precision and uncertainty](#time-precision-and-uncertainty)
4. [Bodies, houses, and angles](#bodies-houses-and-angles)
5. [Aspect families and orb bounds](#aspect-families-and-orb-bounds)
6. [Classical derived formulas](#classical-derived-formulas)
7. [Backend policies](#backend-policies)
8. [Licensing](#licensing)

## Profiles

| Field | Accepted value | Meaning |
|---|---|---|
| `calculation_profile` | `western-tropical-v1` | Tropical, geocentric ecliptic positions of date from the selected ephemeris backend. |
| `aspect_profile` | `ptolemaic-minor-v1` | Separate Ptolemaic and minor aspect families with independently bounded orbs. |
| `derived_profile` | `classical-derived-v1` | Classical dignities, sect, and Lots; present only when `include_derived` is true and the exact chart supports them. |
| `evidence_policy` | `editorial-v1` | Reader-side prioritization and evidence language, documented by the reading skill. |

The request must name the calculation and aspect profiles exactly. The artifact records the derived profile as `null` when derived values are disabled.

## Raw measurements and derived conventions

Treat these as backend measurements:

- normalized UTC instants or UTC intervals and Julian days
- ecliptic longitude, latitude, distance, and longitudinal speed
- backend-returned house cusps and angles
- returned backend flags and software provenance

Treat these as conventions derived from measurements:

- tropical sign labels and sign-boundary sets
- retrograde booleans derived from longitudinal speed
- houses assigned from cusp arcs
- aspect names, families, certainty, and orb policy
- classical dignities, sect, and Lots

Keep derived values under the artifact's `derived` object. Do not describe a derived convention as a raw ephemeris observation.

## Time precision and uncertainty

- Resolve `exact` as one UTC instant. Calculate houses and angles only for this mode.
- Resolve `window` as its closed local interval mapped to UTC.
- Resolve `date-only` from local midnight through the following local midnight.
- Sample every uncertain interval at fifteen-minute steps and include both endpoints.
- Store each uncertain longitude as the smallest circular arc covering all samples, including whether it crosses 0°.
- Emit no exact orb for uncertain comparisons.

Classify an uncertain aspect as `confirmed` only when every sampled source/target pairing remains within the same configured aspect orb. Classify it as `possible` when at least one pairing enters the orb but the condition is not invariant. Omit it when no pairing enters the orb.

Suppress houses, angles, sect, Lots, and overlays whenever either required chart precision does not support them. Record Moon variation, sign crossings, and retrograde-state changes as structured limitations.

## Bodies, houses, and angles

Calculate the Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Ceres, Pallas, Juno, Vesta, mean Lilith, and mean North Node. Derive the South Node exactly opposite the mean North Node.

Treat Chiron, Ceres, Pallas, Juno, and Vesta as optional-file bodies. Omit them with a structured limitation only when their ephemeris data files are unavailable; keep other backend failures fatal.

Accept only these declared house systems:

| Request value | Backend system |
|---|---|
| `placidus` | Placidus |
| `koch` | Koch |
| `campanus` | Campanus |
| `regiomontanus` | Regiomontanus |
| `equal` | Equal |
| `whole-sign` | Whole sign |

Never change house systems automatically. If Placidus or Koch fails near a polar latitude, ask for an explicit `whole-sign` or `equal` rerun.

For exact charts, record Ascendant, Midheaven, Descendant, Imum Coeli, Vertex, and East Point. Calculate directional overlays for the ten planets only, in both source-to-target directions, and only when both charts are exact.

## Aspect families and orb bounds

| Family | Aspects and exact angles | Request bound |
|---|---|---|
| Ptolemaic | conjunction 0°, opposition 180°, trine 120°, square 90°, sextile 60° | `major_orb` from 0 through 15° |
| Minor | semi-sextile 30°, semi-square 45°, quintile 72°, sesquiquadrate 135°, biquintile 144°, quincunx 150° | `minor_orb` from 0 through 3° |

Compare every eligible source body with every eligible target body. Require `major_orb + minor_orb` to be no more than 12°. Together with the family bounds, this prevents positive overlap across every pair of configured aspect angles. Assign the first matching kind in profile order, report each body pair once, and sort exact results by orb with stable body-name tie breaks. A boundary equality resolves by profile order. Exclude duplicate geometry carried by the South Node and East Point from the aspect pass.

The orb constraints are validation limits, not claims that every allowed orb has equal interpretive weight. Reject a request or artifact whose configuration creates positive overlap; never rely on declaration order to hide it.

## Classical derived formulas

Use classical rulerships for the seven traditional planets only. Record dignity states in this order: domicile, exaltation, detriment, fall. Do not add modern rulership assignments.

Define a chart as diurnal when the Sun is in houses 7 through 12, above the horizon; otherwise define it as nocturnal.

Normalize every Lot result to `[0°, 360°)` and apply these formulas:

| Lot | Diurnal formula | Nocturnal formula |
|---|---|---|
| Spirit | Ascendant + Sun − Moon | Ascendant + Moon − Sun |
| Fortune | Ascendant + Moon − Sun | Ascendant + Sun − Moon |
| Marriage | Ascendant + Venus − Sun | Ascendant + Sun − Venus |
| Death | Ascendant + Saturn − Moon | same |
| Sons | Ascendant + Jupiter − Moon | same |
| Daughters | Ascendant + Venus − Moon | same |

Only calculate sect and Lots for an exact chart with the required houses, angle, and bodies.

## Backend policies

`swiss-only` is fail-closed. Request Swiss Ephemeris plus speed flags, inspect every returned flag, and fail if the binding actually uses Moshier, omits speed data, or returns an unrecognized backend. Remediate with a valid `--ephemeris-path`; never label fallback data as Swiss.

`allow-moshier` is an explicit opt-in. Record `requested_backend`, `actual_backend`, numeric return flags, binding version, data path when available, and an `ephemeris-fallback` limitation. It never becomes an invisible default.

Record the IANA zone database as the timezone source unless a reasoned UTC-offset override was used. Preserve the override and its reason in full archival provenance.

## Licensing

The astrology plugin code is licensed under `AGPL-3.0-or-later`. A Swiss Ephemeris professional license is a separate commercial option supplied by Astrodienst; it is not granted by this repository.
