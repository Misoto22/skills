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

## Hybrid Markdown output

The report uses the source language when it is clear, otherwise the language of the request. It uses a fixed relationship-mechanism core followed by evidence-selected real-life domains. This keeps reports comparable without forcing every relationship into four example categories.

The fixed core follows this structure:

```markdown
# Synastry Reading: <Name A> × <Name B>

## Basis and limitations

## Relationship signature

## Reciprocity and asymmetry

## Emotional bond and security

## Attraction, romance, and intimacy

## Communication and mental rhythm

## Conflict, power, and repair

## Trust, boundaries, and commitment

## Growth, values, and shared direction

## Applied life domains
### <Selected domain>

## Overall synthesis
### Strongest connection
### Primary challenge
### What each person should watch
### Practical actions

## Evidence index
```

For Chinese output the fixed headings are translated consistently to `分析基础与限制`, `关系主轴`, `双向影响与不对称性`, `情绪连接与安全感`, `吸引力、浪漫与亲密关系`, `沟通与思维节奏`, `冲突、权力与修复能力`, `信任、边界与承诺`, `共同成长、价值观与人生方向`, `现实领域`, `综合结论`, and `证据索引`. The section order and responsibilities do not change between languages.

The applied-domain section is adaptive. Available modules include:

- friendship, community, and social networks
- daily life, home, family, and care patterns
- career, business, and creative collaboration
- money, shared resources, and risk tolerance
- another topic explicitly requested by the user or strongly activated by the chart

Include every domain the user explicitly requests. If its evidence is weak, say that the source does not support a confident domain-specific reading instead of filling the section with generic astrology. Include an unrequested domain only when it has either two independent major indicators or one tight personal/angle contact plus a directly relevant house overlay. Do not infer that the two people are lovers, friends, colleagues, family, or financial partners unless the request states it.

Each core section and included domain ends with a compact `Evidence`/`星盘证据` list and practical guidance when the cited pattern supports one. Avoid repeating one interpretation across multiple sections; cross-reference the earlier mechanism and explain only its new real-life implication.

Keep every fixed core heading even when the file has little relevant evidence. In that case, state the evidence limit briefly, omit unsupported practical guidance, and do not substitute generic sign descriptions.

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
- The Markdown report contains every fixed relationship-mechanism section in the defined order.
- The applied-domain section includes requested topics and only evidence-qualified additional topics; weak evidence is disclosed rather than padded with generic claims.
- The report distinguishes what each person activates or experiences instead of flattening both overlay directions into one shared effect.
- Every substantive conclusion is traceable to aspects, orbs, or directional house overlays in the source.
- The reading never recomputes the chart, invents missing evidence, predicts events, or assigns a compatibility score.
- Repository validation, formatting, linting, and shell checks pass before publication.
