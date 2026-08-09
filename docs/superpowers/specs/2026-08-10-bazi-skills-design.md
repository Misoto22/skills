# BaZi Skills Design

## Goal

Add a `chinese-metaphysics` plugin whose first published capability turns one or two people's birth details into auditable BaZi data and automatically produces a separate evidence-linked reading. The first release covers static natal analysis and relationship compatibility. It does not cover Da Yun, annual luck, event prediction, Zi Wei Dou Shu, Qi Men Dun Jia, feng shui, or unrelated divination systems.

The public workflow is one request, but calculation and interpretation remain separate artifacts. This keeps calendar facts, model scores, and traditional interpretation distinguishable and independently testable.

## Plugin and skill boundaries

Create one plugin named `chinese-metaphysics` with four skills.

### `bazi-chart`

- Accept one person's birth details.
- Resolve the place, historical civil time, and true solar time.
- Compute one canonical BaZi chart and all declared intermediate values.
- Write `bazi_<name>.json` and `bazi_<name>.md`.
- On success, automatically hand the JSON path to `bazi-reading`.
- Never interpret a chart or calculate relationship compatibility.

### `bazi-reading`

- Accept a complete `bazi_*.json` file, its verified Markdown rendering, or equivalent complete pasted data.
- Write `bazi_reading_<name>.md` beside the source unless the caller requests another output directory.
- Analyze the static natal structure only.
- Never recalculate a chart, predict events, or compare two people.

### `bazi-compatibility`

- Accept two birth records, two existing canonical chart JSON files, or one of each.
- Reuse valid chart JSON files without recalculating them.
- When raw birth details are supplied, invoke the shared calculation core without producing unnecessary single-person readings.
- Compute directional interactions, dimension scores, a general compatibility index, and an optional relationship-specific index.
- Write `bazi_compatibility_<name-a>_<name-b>.json` and `bazi_compatibility_<name-a>_<name-b>.md`.
- On success, automatically hand the compatibility JSON path to `bazi-compatibility-reading`.

### `bazi-compatibility-reading`

- Accept a complete canonical compatibility JSON file, its verified Markdown rendering, or equivalent complete pasted data.
- Write `bazi_compatibility_reading_<name-a>_<name-b>.md`.
- Interpret the comparison without changing either source chart or recomputing scores.
- Never infer an unstated relationship type or reduce the result to one unsupported verdict.

The plugin owns shared calculation and scoring material under `plugins/chinese-metaphysics/shared/`. The repository's shared-sync process vendors the required runtime files into each skill so installed skills never reference `../` or files outside their cache directory.

## Input contracts

### One person

Required fields:

| Field | Meaning |
|---|---|
| `name` | Identifier used in artifacts; it does not affect calculation |
| `birth_place` | Place name to resolve into coordinates and an IANA time zone |
| `birth_date` | Stated birth date |
| `birth_time` | Local civil time, exact to the minute |

Optional or conditional fields:

| Field | Meaning | Default |
|---|---|---|
| `calendar` | `gregorian` or `lunar` | `gregorian` |
| `leap_month` | Whether a stated lunar month is intercalary | Required for an ambiguous lunar month |
| `gender` | User-stated gender for explicitly requested traditional gendered readings | Omitted |
| `latitude`, `longitude` | Exact coordinates supplied by the caller | Resolve from place |
| `timezone` | IANA zone supplied by the caller | Resolve from place |
| `utc_offset` | Explicit historical override with a stated reason | Resolve from the IANA zone |

Never infer gender from a name. If a place name is ambiguous, request enough region or country information to identify it. Place lookup may transmit only the place query; do not send a person's name, birth date, or birth time to a geocoding service.

Gender never changes the four pillars, element distribution, or day-master strength calculation. Use it only when the caller supplied it and explicitly requested a traditional gendered relationship convention; otherwise keep the reading gender-neutral.

### Two people

Accept any of these combinations:

- two complete birth-detail objects;
- two canonical `bazi_*.json` paths;
- one complete birth-detail object and one canonical chart path.

Accept an optional `relationship_type` such as romance, marriage, friendship, family, or work. Without it, compute and interpret only the relationship-neutral dimensions.

## Artifact contracts

### Canonical single chart JSON

The JSON is the reusable machine interface. It contains:

- schema, calculator, rules, and scoring-model versions;
- the stated input and normalization decisions;
- resolved coordinates, IANA zone, historical UTC offset, and daylight-saving state;
- local civil time, UTC, equation-of-time correction, longitude correction, and true solar time;
- distances from relevant hour, day, Li Chun, and monthly solar-term boundaries;
- the four pillars and all derived chart facts;
- raw and adjusted element distributions;
- day-master strength components and score;
- uncertainty, sensitivity, and alternate-boundary results;
- a canonical checksum covering the calculation-bearing fields.

The Markdown file renders the same data for a person to inspect. It is not the machine interface and must not contain interpretation.

### Canonical compatibility JSON

The JSON contains:

- the identity and checksum of both source charts;
- relationship context explicitly supplied by the caller;
- every directional stem, branch, element, Ten-God, and day-pillar interaction used;
- each dimension's supporting evidence, deductions, weight, score, and confidence;
- the general compatibility index;
- a relationship-specific index only when a relationship type is stated;
- score sensitivity under any alternate source chart;
- schema and compatibility-model versions.

Its Markdown rendering remains comparison data, not prose interpretation.

Sanitize artifact name components to portable slugs while preserving the original display names inside the files. Do not overwrite an existing artifact whose canonical input checksum differs. Add a deterministic short checksum suffix when two different records resolve to the same filename.

## Authoritative calculation basis

Separate official calendar and astronomical authority from BaZi convention.

- Use `GB/T 33661-2017`, *Calculation and promulgation of the Chinese calendar*, as the Chinese-calendar and solar-term reference standard.
- Use published Purple Mountain Observatory calendar and solar-term values as golden fixtures.
- Use Swiss Ephemeris backed by JPL ephemerides for runtime solar longitude and equation-of-time calculations.
- Use the IANA Time Zone Database to resolve historical civil offsets and daylight-saving transitions.
- Use `lunar-python` only as a cross-check in development or tests, not as the authoritative runtime source.

The official sources establish dates, instants, and astronomical positions. They do not establish BaZi interpretation, day-boundary convention, strength weights, or compatibility weights.

## Fixed BaZi conventions

Version the following convention set as one coherent rules profile:

- supported birth years: 1900 through 2100 inclusive;
- true solar time determines the hour branch and the configured day boundary;
- the year pillar changes at the exact Li Chun instant;
- the month pillar changes at the exact instant of each of the twelve `jie`, not on a lunar month boundary;
- the day pillar changes at 23:00 true solar time (`zi chu`);
- a birth at 23:00–23:59 true solar time also receives a 00:00-boundary alternate chart;
- a lunar input follows the standardized Chinese calendar and must identify an intercalary month when applicable.

Compute the sexagenary day from a tested astronomical-day anchor rather than a hand-maintained date table. Compare solar-term boundaries as instants in UTC, then display them in the relevant local civil and true-solar representations.

## Raw chart contents

Record at least:

- four pillar stems and branches, yin-yang, and elements;
- day master;
- visible and hidden Ten Gods;
- hidden stems and their declared base weights;
- month command, roots, and exposed stems;
- Na Yin, Twelve Stages, and Xun Kong;
- stem combinations and controls;
- branch combinations, meetings, clashes, punishments, harms, and breaks;
- common Shen Sha as explicitly secondary evidence;
- every scoring input and intermediate value.

Do not silently apply a claimed transformation. Record the prerequisites, whether each prerequisite passed, and the effect the scoring model applied.

## Scoring model

All scores are deterministic outputs of a named, versioned heuristic model. They are auditable and reproducible, not official measurements or probabilities.

### Element percentages

Produce two distributions that each normalize to 100 percent:

1. `base_distribution` from visible stems and the declared hidden-stem shares.
2. `adjusted_distribution` after seasonal state, root depth, exposure, valid transformations, controls, production, and drainage.

List every contribution before normalization. Do not equate character count with effective strength.

### Day-master strength

Produce a 0–100 score where 50 is the model's balance center. Break the score into:

- seasonal support;
- roots and positional support;
- visible support;
- control, production, drainage, and structural interactions.

Show every addition and deduction. Determine special or following structures through separate prerequisite rules; a numeric threshold alone cannot declare a following structure.

### Compatibility

Produce five relationship-neutral dimensions:

1. element and favorable-element complementarity;
2. day-master support and drain in both directions;
3. stem and branch combinations, controls, clashes, punishments, harms, and breaks;
4. day-pillar and relationship-core interaction;
5. structural stability, reciprocity, and transformation.

Expose the weight, evidence, deduction, and result for every dimension. Combine them into a 0–100 general index. A declared relationship type selects a versioned weight profile and produces a separate contextual index; it does not overwrite the general index.

Every score carries:

- the model version;
- exact weights and arithmetic;
- positive and negative evidence;
- confidence level and its reasons;
- alternate-chart sensitivity where applicable.

Reports must say `78/100 under model <version>`, not `78% objectively compatible`.

## Single-person reading

Write these sections in order:

1. basis and limitations;
2. chart summary, element distributions, and day-master strength score;
3. day master, month command, and overall flow;
4. structure, transformation, and favorable or unfavorable tendencies;
5. primary strengths and structural tensions;
6. personality and behavioral tendencies;
7. interpersonal and intimate-relationship tendencies;
8. working style, capabilities, and favorable environments;
9. practical actions;
10. evidence index.

The first release remains static. It does not calculate Da Yun, annual luck, or event timing. A future forecasting capability must be a separate design and skill.

## Compatibility reading

Write these sections in order:

1. basis, stated relationship type, and limitations;
2. general and contextual scorecards;
3. complementarity and mutual drain;
4. directional support and asymmetry;
5. attraction, affinity, and relationship-core interaction;
6. communication and collaboration patterns;
7. conflict sources and repair capacity;
8. stability, boundaries, and long-term conditions;
9. the explicitly requested relationship module;
10. strongest connection, primary challenge, and actions for each person;
11. evidence index.

Do not infer that two people are romantic partners, relatives, friends, or colleagues. Every substantive paragraph must cite source-chart facts, a directional interaction, or a score component. Use conditional traditional-interpretation language. Do not predict events, diagnose health or psychology, or present medical, legal, or financial advice.

## Failure and uncertainty handling

Stop without a complete data or reading artifact when:

- the birth minute is missing or approximate;
- the place cannot be uniquely resolved;
- an ambiguous lunar month lacks the leap-month flag;
- a civil time falls in a daylight-saving fold or gap and the actual occurrence cannot be identified;
- the date falls outside 1900–2100;
- independent runtime invariants disagree, such as a failed calendar round-trip or inconsistent day-pillar derivation;
- a supplied canonical JSON file fails its schema, version, required-field, or checksum validation.

Never substitute noon, guess a city, infer gender, or invent a missing pillar.

Continue with reduced confidence and explicit sensitivity output when:

- true solar time is near an hour boundary;
- true solar time falls from 23:00 through 23:59;
- the birth instant is near Li Chun or a monthly `jie`;
- only a city-center coordinate is available;
- the primary and alternate charts change the favorable elements, strength class, or compatibility conclusion.

Invoke a reading skill only after the corresponding canonical data artifact exists and validates.

## Testing strategy

Write tests before implementation.

### Calculation and scoring tests

- Golden-test lunar dates and solar-term instants against Purple Mountain Observatory publications.
- Cross-check the golden fixtures with an independent library; any unexplained core-pillar disagreement blocks release rather than becoming a per-request runtime dependency.
- Test one minute before, at, and one minute after Li Chun and every monthly `jie`.
- Test true-solar corrections that stay within an hour, cross an hour branch, cross 23:00, and cross a civil date.
- Test daylight-saving starts, ends, repeated local times, and nonexistent local times outside China.
- Verify that the sexagenary day advances by one and repeats every 60 days.
- Verify that each element distribution sums to 100 within the declared rounding tolerance.
- Verify every score remains in 0–100 and can be recomputed from its ledger.
- Verify that swapping the two people preserves symmetric general scores while swapping all directional evidence correctly.
- Verify deterministic JSON and scores for identical inputs under the same dependency and model versions.
- Preserve all boundary and alternate-chart cases as regression fixtures.

### Skill routing evaluations

- One raw birth record routes to `bazi-chart`, not either reading or compatibility skill.
- A completed single chart plus an interpretation request routes to `bazi-reading`.
- Two raw records, two canonical charts, or one of each route to `bazi-compatibility`.
- Completed compatibility data plus an interpretation request routes to `bazi-compatibility-reading`.
- A single chart never triggers compatibility.
- Missing or corrupt source data never triggers a reading.

### Repository acceptance

- Each published skill has `SKILL.md`, `agents/openai.yaml`, registry entries, and evaluation cases.
- Every skill shipping scripts has unit tests.
- Shared runtime copies remain synchronized.
- `python3 scripts/validate-repository.py`, `uvx ruff check .`, `uvx ruff format .`, and `shellcheck scripts/*.sh` pass before release.

## Acceptance criteria

- A single request produces a canonical chart and a separate static reading without asking for a second request.
- A compatibility request reuses existing canonical charts and produces separate comparison data and interpretation artifacts.
- Machine consumers read JSON rather than parsing rendered Markdown.
- Every time correction, boundary rule, scoring contribution, and model version is visible and reproducible.
- Official calendar and astronomical sources are not misrepresented as authorities for traditional interpretation.
- Scores remain explainable heuristics and never appear without their evidence and confidence.
- Alternate boundary rules are surfaced whenever they materially change the chart or reading.
- No skill hard-codes a person's identity or birth data.
- No first-release skill calculates Da Yun, annual luck, or concrete event predictions.
