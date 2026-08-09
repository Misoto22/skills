# Synastry Reading Skill Design

## Goal

Add a second skill to the existing `astrology` plugin that interprets a completed synastry data file. The current `synastry` skill remains the deterministic calculation layer. After a successful calculation it immediately hands the generated data file to the new `synastry-reading` skill, which writes a separate Markdown reading without asking for another confirmation.

## Skill boundaries

### `synastry`

- Accepts exactly two sets of birth details.
- Requires both birth times to the minute.
- Computes the natal charts, cross-chart aspects, and both house-overlay directions with Swiss Ephemeris.
- Writes `synastry_<name-a>_<name-b>.txt` as measurement data only.
- On success, immediately invokes `synastry-reading` with the written file path.
- On calculation, dependency, or input failure, stops without requesting or inventing an interpretation.

### `synastry-reading`

- Accepts a completed `synastry_*.txt` file or equivalent pasted synastry data containing two natal charts, cross-chart aspects with orbs, and both house-overlay directions.
- May be invoked by the calculation hand-off or directly when a user asks to interpret an existing synastry file.
- Never recomputes positions, changes orbs, or substitutes missing placements.
- Writes `synastry_reading_<name-a>_<name-b>.md` beside the source file unless the caller names another output directory.
- Is not for raw birth details, a single natal chart, transit work, forecasting, or interpreting a chart from memory.

The analysis skill contains instructions, a fixed template, and worked examples only. It has no Python or third-party dependency. This keeps the execution-environment concern isolated to the calculator.

## Automatic hand-off

The calculator owns the workflow transition:

1. Validate both birth records.
2. Compute and write the data file.
3. Report the data-file path and any degraded ephemeris coverage.
4. Immediately invoke `synastry-reading` with that exact file.
5. Return both output paths and a short neutral overview after the Markdown file is written.

The hand-off occurs only after the data file exists. If analysis cannot read a complete source, it names the missing section and stops; it does not produce a partial report that could be mistaken for a complete reading.

## Interpretation method

Every interpretive claim must cite one or more measured facts from the source file. Evidence is prioritized in this order:

1. Tight Ptolemaic aspects involving the Sun, Moon, Mercury, Venus, Mars, Ascendant, or Midheaven.
2. Repeated themes across more than one major aspect.
3. Relevant house overlays in both directions.
4. Outer-planet, node, asteroid, lot, and minor-aspect contacts as supporting evidence rather than the sole basis for a strong conclusion.

Each cited aspect includes both bodies, aspect type, and orb. Each cited overlay names whose body falls into whose house. Missing asteroid data and coordinate or time limitations are repeated in the Markdown report. The reading uses conditional language, does not predict events, does not assign compatibility scores, and does not frame any placement as proof of a person's character or fate.

## Fixed Markdown output

The report uses the source language when it is clear, otherwise the language of the request. It always follows this structure:

```markdown
# Synastry Reading: <Name A> × <Name B>

## Basis and limitations

## Relationship overview

## Love
### Core dynamic
### Supportive patterns
### Friction and risks
### Chart evidence
### Practical guidance

## Friendship
### Core dynamic
### Supportive patterns
### Boundaries and risks
### Chart evidence
### Practical guidance

## Business partnership
### Roles and complementary strengths
### Communication and decision-making
### Power and conflict risks
### Chart evidence
### Collaboration guidance

## Money
### Money attitudes and security
### Shared-resource patterns
### Financial risks
### Chart evidence
### Financial boundaries

## Overall synthesis
### Strongest connection
### Primary challenge
### Three practical actions

## Evidence index
```

For Chinese output the headings are translated consistently to `分析基础与限制`, `关系总览`, `爱情`, `友情`, `事业合作`, `金钱`, `综合结论`, and `证据索引`. The section order and subsection responsibilities do not change between languages.

## Failure handling

- Missing source file: ask for the file or its contents.
- Missing one natal chart, the aspect table, or either overlay direction: identify the missing section and stop.
- Missing optional ephemeris bodies explicitly recorded in the source: continue, repeat the limitation, and avoid claims relying on those bodies.
- Unsupported language: follow the user's language while preserving body names, aspect types, and orbs accurately.
- Conflicting duplicated measurements: quote the conflict and stop rather than choosing one silently.

## Repository changes

- Scaffold `plugins/astrology/skills/synastry-reading/` through `scripts/new-skill.py` so every marketplace registry stays synchronized.
- Add the new skill instructions, `agents/openai.yaml`, an output-template reference, and worked examples.
- Update `synastry` instructions and examples to require the automatic hand-off while preserving the raw data-only file.
- Add an evaluation suite for routing and analysis behavior, and update the calculator evaluation to expect the hand-off.
- Add contract tests only where executable repository behavior needs protection; the prose skill's behavioral evaluation cases remain its primary tests.

## Acceptance criteria

- Two birth records route to `synastry`, not `synastry-reading`.
- A completed synastry file plus an interpretation request routes to `synastry-reading`.
- A successful calculation automatically continues into the reading skill.
- The raw `.txt` file contains measurements only.
- The Markdown report contains all four relationship dimensions and the fixed headings.
- Every substantive conclusion is traceable to aspects, orbs, or directional house overlays in the source.
- The reading never recomputes the chart, invents missing evidence, predicts events, or assigns a compatibility score.
- Repository validation, formatting, linting, and shell checks pass before publication.
