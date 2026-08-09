# BaZi Skill Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a four-skill `chinese-metaphysics` plugin that calculates auditable single-person BaZi charts, reads them, compares two charts with transparent scores, and writes a separate compatibility reading.

**Architecture:** Keep astronomy, calendrical rules, pillar derivation, relations, scoring, schema validation, and artifact naming in one canonical plugin-level `shared/` implementation that the repository vendors into every installed skill. The two calculator skills expose thin CLIs over that core and write canonical JSON plus data-only Markdown; the two prose skills validate and interpret those artifacts without recalculation.

**Tech Stack:** Python 3.11+, standard library (`argparse`, `dataclasses`, `datetime`, `hashlib`, `json`, `zoneinfo`), optional runtime `pyswisseph`, Markdown/YAML skill instructions, JSON evaluation suites, Python `unittest`, repository validation scripts.

## Global Constraints

- Support birth years 1900 through 2100 inclusive.
- Use `GB/T 33661-2017` and Purple Mountain Observatory fixtures for calendar and solar-term validation.
- Use Swiss Ephemeris/JPL calculations at runtime; keep the import lazy so validation and unit tests run without the dependency.
- Resolve historical civil offsets with the IANA Time Zone Database.
- Use true solar time, exact Li Chun and monthly `jie`, and a 23:00 true-solar day boundary.
- Produce an alternate 00:00-boundary chart for births from 23:00 through 23:59 true solar time.
- Treat all percentages and 0–100 scores as versioned, auditable heuristic-model outputs, never probabilities or official measurements.
- Keep canonical JSON machine-readable and Markdown data-only; interpretation belongs in separate reading files.
- Do not hard-code a person's identity or birth data, infer gender, guess missing minutes or places, or overwrite an artifact with a different input checksum.
- Do not calculate Da Yun, annual luck, event timing, or concrete predictions in the first release.
- Keep runtime content organization-neutral and free of local absolute paths, `../`, and `${CLAUDE_*}`.
- Keep all code identifiers, comments, documentation, and commit messages in English.
- Write tests before each implementation increment.

---

### Task 1: Scaffold and register the four-skill plugin

**Files:**
- Create through scaffold: `plugins/chinese-metaphysics/`
- Create: `tests/bazi_skill/__init__.py`
- Create: `tests/bazi_skill/test_skill_contract.py`
- Modify through scaffold: `.claude-plugin/marketplace.json`
- Modify through scaffold: `.version-bump.json`
- Modify through scaffold: `bundle/.claude-plugin/plugin.json`
- Modify through scaffold: `README.md`
- Modify through scaffold: `README.zh-CN.md`
- Modify through scaffold: `scripts/validate-repository.py`
- Modify through scaffold: `skills.sh.json`

**Interfaces:**
- Consumes: the repository's `scripts/new-skill.py` registration workflow.
- Produces: `/chinese-metaphysics:bazi-chart`, `/chinese-metaphysics:bazi-reading`, `/chinese-metaphysics:bazi-compatibility`, and `/chinese-metaphysics:bazi-compatibility-reading` as registered but initially RED skills.

- [ ] **Step 1: Scaffold all skills with the repository helper**

```bash
python3 scripts/new-skill.py chinese-metaphysics bazi-chart --category learning
python3 scripts/new-skill.py chinese-metaphysics bazi-reading --category learning
python3 scripts/new-skill.py chinese-metaphysics bazi-compatibility --category learning
python3 scripts/new-skill.py chinese-metaphysics bazi-compatibility-reading --category learning
```

Expected: the first call creates both plugin manifests; later calls update every registry without hand-editing skill names.

- [ ] **Step 2: Write the failing publication contract**

Create `tests/bazi_skill/test_skill_contract.py` with assertions for the four exact skill names, versions, automatic hand-off phrases, JSON/Markdown artifact names, no hard-coded personal birth data, and a body length below 500 lines for each `SKILL.md`:

```python
SKILLS = {
    "bazi-chart": ("bazi_<name>.json", "bazi-reading"),
    "bazi-reading": ("bazi_reading_<name>.md", None),
    "bazi-compatibility": ("bazi_compatibility_<name-a>_<name-b>.json", "bazi-compatibility-reading"),
    "bazi-compatibility-reading": ("bazi_compatibility_reading_<name-a>_<name-b>.md", None),
}
```

- [ ] **Step 3: Verify RED**

Run: `python3 -m unittest tests.bazi_skill.test_skill_contract -v`

Expected: FAIL because scaffold placeholders do not declare the approved contracts.

- [ ] **Step 4: Replace mechanical plugin placeholders**

Use the synchronized manifest description:

`BaZi charts and relationship compatibility built from auditable calendar data, transparent scores, and separate evidence-linked readings.`

Use keywords `bazi`, `four-pillars`, `chinese-calendar`, `compatibility`, and `ten-gods`. Describe the `skills.sh.json` group as BaZi calculation and interpretation, not as a general-purpose fortune-telling bundle.

- [ ] **Step 5: Commit the registered surface**

```bash
git add .claude-plugin/marketplace.json .version-bump.json bundle README.md README.zh-CN.md \
  plugins/chinese-metaphysics scripts/validate-repository.py skills.sh.json tests/bazi_skill
git commit -m "feat: scaffold BaZi skill suite"
```

### Task 2: Build request parsing and civil-time normalization

**Files:**
- Create: `plugins/chinese-metaphysics/shared/bazi/__init__.py`
- Create: `plugins/chinese-metaphysics/shared/bazi/models.py`
- Create: `plugins/chinese-metaphysics/shared/bazi/timekeeping.py`
- Create: `tests/bazi_skill/test_timekeeping.py`
- Modify: `.coveragerc`

**Interfaces:**
- Produces: `BirthInput.from_mapping(payload: Mapping[str, Any]) -> BirthInput`.
- Produces: `resolve_civil_time(birth: BirthInput) -> CivilMoment`.
- Produces: `apply_true_solar_time(birth: BirthInput, moment: CivilMoment, equation_of_time_days: float) -> NormalizedMoment`.
- `CivilMoment` exposes `local`, `utc`, `utc_offset_minutes`, and `fold`; `NormalizedMoment` adds `longitude_correction_minutes`, `equation_of_time_minutes`, and `true_solar`.

- [ ] **Step 1: Write failing validation and DST tests**

Cover exact `HH:MM`, supported years, Gregorian/lunar enum values, leap-month requirements, coordinate limits, IANA lookup failures, explicit-offset overrides, New York's 2021 fall-back fold, New York's 2021 spring gap, Shanghai historical offset resolution, and true-solar date rollover.

```python
with self.assertRaisesRegex(BirthDataError, "minute"):
    BirthInput.from_mapping({**VALID, "birth_time": "07"})
with self.assertRaisesRegex(BirthDataError, "ambiguous"):
    resolve_civil_time(BirthInput.from_mapping({**NY, "birth_date": "2021-11-07", "birth_time": "01:30"}))
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.bazi_skill.test_timekeeping -v`

Expected: FAIL because the shared package does not exist.

- [ ] **Step 3: Implement immutable request and time models**

Define `BirthInput`, `CivilMoment`, and `NormalizedMoment` as frozen dataclasses. Aggregate all request faults in `BirthDataError.problems`. Detect folds and gaps by round-tripping both `fold=0` and `fold=1` candidates through UTC. Use an explicit offset only when the request carries it.

Compute apparent local time without a time-zone meridian shortcut:

```python
longitude_correction = 4.0 * birth.longitude - moment.utc_offset_minutes
true_solar = moment.local.replace(tzinfo=None) + timedelta(
    minutes=longitude_correction + equation_of_time_days * 1440.0
)
```

- [ ] **Step 4: Exclude vendored shared copies from duplicate coverage accounting**

Add this to `.coveragerc` while keeping the canonical plugin-level source measured:

```ini
[run]
omit =
    plugins/*/skills/*/shared/*
```

- [ ] **Step 5: Verify GREEN and commit**

```bash
python3 -m unittest tests.bazi_skill.test_timekeeping -v
git add .coveragerc plugins/chinese-metaphysics/shared tests/bazi_skill/test_timekeeping.py
git commit -m "feat: normalize BaZi birth times"
```

### Task 3: Add the astronomical backend and Chinese-calendar conversion

**Files:**
- Create: `plugins/chinese-metaphysics/shared/bazi/ephemeris.py`
- Create: `plugins/chinese-metaphysics/shared/bazi/calendar.py`
- Create: `tests/bazi_skill/fixtures/pmo-calendar.json`
- Create: `tests/bazi_skill/test_calendar.py`

**Interfaces:**
- Produces protocol `Ephemeris` with `julian_day(datetime)`, `from_julian_day(float)`, `sun_longitude(float)`, `moon_longitude(float)`, and `equation_of_time(float)`.
- Produces `SwissEphemeris`, whose constructor lazily imports `swisseph`.
- Produces `solar_term_instant(year: int, longitude: float, ephemeris: Ephemeris) -> datetime`.
- Produces `lunar_to_gregorian(year: int, month: int, day: int, leap: bool, ephemeris: Ephemeris) -> date`.

- [ ] **Step 1: Add failing official-fixture tests**

Record source URLs and available PMO values for representative lunar New Years, leap months, Li Chun, Jing Zhe, and winter solstice across 1900, 1950, 2000, and 2026. Cover the 2100 upper boundary with an independently calculated fixture under the same national-standard rules rather than attributing an unpublished value to PMO. Test exact dates and a solar-term tolerance of 60 seconds for a real Swiss integration run when `swisseph` is available; use a deterministic fake ephemeris for root-finding unit tests.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.bazi_skill.test_calendar -v`

Expected: FAIL on missing calendar functions.

- [ ] **Step 3: Implement wrapped-angle root finding**

Bracket each solar-longitude crossing and each Sun-Moon conjunction, unwrap the angular residual around zero, and bisect until the time interval is below 0.5 seconds. Reject an unbracketed root instead of returning the closest sample.

```python
def signed_angle(value: float, target: float) -> float:
    return (value - target + 180.0) % 360.0 - 180.0
```

- [ ] **Step 4: Implement the standardized lunar-month sequence**

Calculate new moons surrounding consecutive winter solstices in Beijing civil time. Number the month containing winter solstice as month 11. In a 13-month sui, mark the first following lunar month without a principal term as leap. Convert the requested lunar day by adding `day - 1` Beijing calendar days to the selected new-moon day; reject nonexistent days.

- [ ] **Step 5: Add the lazy Swiss adapter**

Use `swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)` and the Moon equivalent for apparent geocentric ecliptic longitude, and `swe.time_equ(jd)` for equation of time. On missing `pyswisseph`, raise one actionable `EphemerisUnavailable` message.

- [ ] **Step 6: Verify with and without Swiss and commit**

```bash
python3 -m unittest tests.bazi_skill.test_calendar -v
uv run --with pyswisseph python3 -m unittest tests.bazi_skill.test_calendar -v
git add plugins/chinese-metaphysics/shared tests/bazi_skill
git commit -m "feat: compute BaZi calendar boundaries"
```

### Task 4: Derive four pillars and structural chart facts

**Files:**
- Create: `plugins/chinese-metaphysics/shared/bazi/pillars.py`
- Create: `plugins/chinese-metaphysics/shared/bazi/relations.py`
- Create: `plugins/chinese-metaphysics/shared/rules/chart-v1.json`
- Create: `tests/bazi_skill/test_pillars.py`
- Create: `tests/bazi_skill/test_relations.py`

**Interfaces:**
- Produces `calculate_pillars(birth: BirthInput, moment: NormalizedMoment, ephemeris: Ephemeris) -> FourPillars`.
- Produces `derive_chart_facts(pillars: FourPillars, rules: Mapping[str, Any]) -> dict[str, Any]`.
- Produces `alternate_midnight_pillars(...) -> FourPillars | None` only for 23:00–23:59 true-solar births.
- Defines frozen `Pillar` and `FourPillars` dataclasses in `pillars.py`; `FourPillars` contains `year`, `month`, `day`, and `hour` pillars plus boundary metadata.

- [ ] **Step 1: Write failing pillar boundary tests**

Cover one minute before and at Li Chun, one minute before and at every monthly `jie`, 22:59/23:00/23:59/00:00 true-solar day boundaries, all twelve hour branches, the five day-stem-to-Zi-hour groups, and a 60-day progression from a documented Jia-Zi anchor.

- [ ] **Step 2: Write failing structural-fact tests**

Assert the versioned hidden-stem table, Ten-God derivation from element and polarity, Na Yin, Twelve Stages, Xun Kong, stem combinations, branch six combinations, three combinations, three meetings, clashes, punishments, harms, and breaks. Assert that a transformation is recorded as `candidate` until every declared prerequisite passes.

- [ ] **Step 3: Verify RED**

Run: `python3 -m unittest tests.bazi_skill.test_pillars tests.bazi_skill.test_relations -v`

Expected: FAIL because no pillar or relation engine exists.

- [ ] **Step 4: Implement pillar formulas**

Use zero-based stem and branch indexes. Derive month stem with `(year_stem * 2 + month_branch_index) % 10` after mapping Li Chun to Yin month. Derive hour branch with `((hour + 1) // 2) % 12` and hour stem with `(day_stem * 2 + hour_branch) % 10`. Derive the sexagenary day from one fixture-backed Julian-day anchor and apply the configured 23:00 date increment before indexing.

- [ ] **Step 5: Implement rule-table structural facts**

Keep all fixed mappings and transformation prerequisites in `chart-v1.json`. Code evaluates and records rules; it does not hide doctrine in branching literals. Mark Shen Sha as `secondary` in every emitted record.

- [ ] **Step 6: Verify GREEN and commit**

```bash
python3 -m unittest tests.bazi_skill.test_pillars tests.bazi_skill.test_relations -v
git add plugins/chinese-metaphysics/shared tests/bazi_skill
git commit -m "feat: derive BaZi chart structure"
```

### Task 5: Implement transparent element and day-master scoring

**Files:**
- Create: `plugins/chinese-metaphysics/shared/bazi/scoring.py`
- Create: `plugins/chinese-metaphysics/shared/rules/scoring-v1.json`
- Create: `plugins/chinese-metaphysics/shared/references/scoring-method.md`
- Create: `tests/bazi_skill/test_scoring.py`

**Interfaces:**
- Produces `score_chart(pillars: FourPillars, facts: Mapping[str, Any], rules: Mapping[str, Any]) -> dict[str, Any]`.
- Returned object contains `base_distribution`, `adjusted_distribution`, `day_master_strength`, `special_structure`, `ledger`, `confidence`, and `model_version`.

- [ ] **Step 1: Write failing ledger and invariant tests**

Test that both distributions sum to 100 within `0.01`, every visible and hidden contribution appears before normalization, the strength score stays in 0–100, changing one support root changes only documented ledger entries, invalid transformations contribute nothing, and a numeric threshold alone never sets a following structure.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.bazi_skill.test_scoring -v`

Expected: FAIL on missing scorer.

- [ ] **Step 3: Define the complete v1 model table**

In `scoring-v1.json`, declare hidden-stem shares, seasonal multipliers, root-position weights, exposed-stem weights, relation adjustments, strength thresholds, confidence thresholds, rounding, and the exact model id `bazi-score-v1`. Use default seasonal multipliers `旺=1.40`, `相=1.20`, `休=1.00`, `囚=0.80`, `死=0.60`; every later change requires a new model id.

- [ ] **Step 4: Implement ledger-first scoring**

Build named contribution records first, sum them second, and normalize last. Calculate strength from separately named seasonal, root, visible-support, control, production, drainage, and structural components. Clamp only at the final boundary and record any clamp.

- [ ] **Step 5: Document the method and limits**

Explain every weight, the distinction between base and adjusted distribution, why scores are heuristics, and how alternate charts affect confidence. Do not claim that GB/T, PMO, JPL, or Swiss Ephemeris endorses the scoring model.

- [ ] **Step 6: Verify GREEN and commit**

```bash
python3 -m unittest tests.bazi_skill.test_scoring -v
git add plugins/chinese-metaphysics/shared tests/bazi_skill/test_scoring.py
git commit -m "feat: score BaZi chart structure"
```

### Task 6: Ship the single-chart calculator and artifact contract

**Files:**
- Create: `plugins/chinese-metaphysics/shared/bazi/artifacts.py`
- Create: `plugins/chinese-metaphysics/skills/bazi-chart/scripts/compute_chart.py`
- Create: `plugins/chinese-metaphysics/skills/bazi-chart/references/request.example.json`
- Create: `plugins/chinese-metaphysics/skills/bazi-chart/references/examples.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-chart/SKILL.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-chart/agents/openai.yaml`
- Create: `tests/bazi_skill/test_artifacts.py`
- Create: `tests/bazi_skill/test_compute_chart.py`
- Create: `evals/bazi-chart/evals.json`

**Interfaces:**
- Produces CLI `compute_chart.py --request PATH|--json JSON --out DIR [--language en|zh] [--ephemeris-path DIR]`.
- Produces `bazi_<slug>.json` and `bazi_<slug>.md` and prints both exact paths.
- The chart skill hands the validated JSON path to `bazi-reading` after success.

- [ ] **Step 1: Write failing CLI and artifact tests**

Cover valid files, inline JSON, Chinese names, path traversal names, same-name/different-checksum suffixing, no overwrite, canonical key ordering, checksum verification, data-only Markdown, output-directory creation, invalid input exit code 2, and missing Swiss dependency messaging.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.bazi_skill.test_artifacts tests.bazi_skill.test_compute_chart -v`

Expected: FAIL because neither artifact writer nor CLI exists.

- [ ] **Step 3: Implement canonical serialization and filenames**

Hash canonical UTF-8 JSON with sorted keys and compact separators, excluding the checksum field itself. Preserve display names in content. Use Unicode-safe portable slugs, `unnamed` fallback, and an eight-hex checksum suffix only on a conflicting existing path.

- [ ] **Step 4: Implement the thin CLI**

Parse once, normalize once, calculate once, score once, validate the envelope, then write both artifacts atomically through temporary files in the destination directory. Do not write either final file after a failed calculation.

- [ ] **Step 5: Replace skill placeholders and add evals**

Document place lookup, exact-minute refusal, global IANA resolution, official-versus-traditional boundaries, command usage, output sections, automatic hand-off, privacy, and limits. Add at least four triggers, three non-triggers, and behavior cases for ambiguous place, missing minute, boundary alternate, and successful hand-off.

- [ ] **Step 6: Sync shared runtime, verify GREEN, and commit**

```bash
python3 scripts/sync-shared.py
python3 -m unittest tests.bazi_skill.test_artifacts tests.bazi_skill.test_compute_chart -v
python3 scripts/run-evals.py --check
git add plugins/chinese-metaphysics evals/bazi-chart tests/bazi_skill
git commit -m "feat: generate auditable BaZi charts"
```

### Task 7: Add the evidence-linked single reading

**Files:**
- Modify: `plugins/chinese-metaphysics/skills/bazi-reading/SKILL.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-reading/agents/openai.yaml`
- Create: `plugins/chinese-metaphysics/skills/bazi-reading/references/output-template.md`
- Create: `plugins/chinese-metaphysics/skills/bazi-reading/references/examples.md`
- Create: `evals/bazi-reading/evals.json`

**Interfaces:**
- Consumes: validated `bazi_*.json`, its verified Markdown rendering, or complete equivalent pasted data.
- Produces: `bazi_reading_<slug>.md` with the ten approved sections and a deduplicated evidence index.

- [ ] **Step 1: Write RED behavior evaluations**

Add cases for calculator hand-off, direct existing-file reading, pasted complete data, corrupt checksum, missing hour pillar, alternate chart sensitivity, raw birth details routing to `bazi-chart`, and forecast requests staying out.

- [ ] **Step 2: Validate evaluation structure**

Run: `python3 scripts/run-evals.py --check`

Expected: JSON schema passes while scaffold content remains behaviorally RED.

- [ ] **Step 3: Implement the reading instructions**

Require full-source validation, an evidence ledger, fixed section order, inline references to exact pillars/relations/score-ledger ids, conditional traditional language, alternate-chart comparison, and no recalculation. Keep Shen Sha secondary and prohibit event prediction, medical/psychological diagnosis, and unrequested gendered conventions.

- [ ] **Step 4: Add bilingual template and worked examples**

Provide consistent English and Chinese headings for basis, scores, day master/month command, structure and favorable tendencies, strengths/tensions, behavior, relationships, work, actions, and evidence index. Show one complete hand-off, one alternate-boundary report excerpt, and one corrupt-source refusal.

- [ ] **Step 5: Verify contracts and commit**

```bash
python3 scripts/run-evals.py --check
python3 -m unittest tests.bazi_skill.test_skill_contract -v
git add plugins/chinese-metaphysics/skills/bazi-reading evals/bazi-reading
git commit -m "feat: add BaZi natal readings"
```

### Task 8: Implement compatibility evidence and scores

**Files:**
- Create: `plugins/chinese-metaphysics/shared/bazi/compatibility.py`
- Create: `plugins/chinese-metaphysics/shared/rules/compatibility-v1.json`
- Create: `plugins/chinese-metaphysics/shared/references/compatibility-method.md`
- Create: `plugins/chinese-metaphysics/skills/bazi-compatibility/scripts/compute_compatibility.py`
- Create: `plugins/chinese-metaphysics/skills/bazi-compatibility/references/request.example.json`
- Create: `plugins/chinese-metaphysics/skills/bazi-compatibility/references/examples.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-compatibility/SKILL.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-compatibility/agents/openai.yaml`
- Create: `tests/bazi_skill/test_compatibility.py`
- Create: `tests/bazi_skill/test_compute_compatibility.py`
- Create: `evals/bazi-compatibility/evals.json`

**Interfaces:**
- Produces `compare_charts(left: Mapping[str, Any], right: Mapping[str, Any], relationship_type: str | None) -> dict[str, Any]`.
- Produces CLI accepting two chart paths, two embedded birth objects, or one of each.
- Produces compatibility JSON/Markdown and hands the JSON path to `bazi-compatibility-reading`.

- [ ] **Step 1: Write failing symmetry and scoring tests**

Assert that swapping people preserves the general total and five dimension scores while reversing directional evidence owners; relationship profiles change only the contextual index; unknown relationship types fail; all arithmetic is reproducible; alternate source charts produce a sensitivity range; and no single Shen Sha changes a dimension by itself.

- [ ] **Step 2: Write failing mixed-input CLI tests**

Cover chart+chart, raw+raw with an injected fake ephemeris, chart+raw, invalid checksum, mismatched schema version, collision-safe artifacts, data-only Markdown, and automatic hand-off wording.

- [ ] **Step 3: Verify RED**

Run: `python3 -m unittest tests.bazi_skill.test_compatibility tests.bazi_skill.test_compute_compatibility -v`

Expected: FAIL on missing comparator and CLI.

- [ ] **Step 4: Define and implement the compatibility model**

Use exact general weights `25/20/20/20/15` for element complementarity, directional day-master support, stem/branch interactions, day-pillar core, and structural stability. Put romance, marriage, friendship, family, and work profiles in `compatibility-v1.json`; calculate a separate contextual score rather than replacing the general score. Keep a complete positive/negative evidence ledger for every dimension.

- [ ] **Step 5: Implement mixed-input orchestration**

Validate existing chart checksums and versions. Calculate raw records through the shared core without invoking `bazi-reading`. Compare only validated canonical envelopes, then write compatibility artifacts atomically.

- [ ] **Step 6: Replace skill placeholders and add evals**

Document accepted input combinations, relationship-neutral default, reusable charts, score semantics, output contract, failure behavior, and automatic reading hand-off. Add routing cases that exclude one-person readings and existing compatibility interpretations.

- [ ] **Step 7: Sync, verify GREEN, and commit**

```bash
python3 scripts/sync-shared.py
python3 -m unittest tests.bazi_skill.test_compatibility tests.bazi_skill.test_compute_compatibility -v
python3 scripts/run-evals.py --check
git add plugins/chinese-metaphysics evals/bazi-compatibility tests/bazi_skill
git commit -m "feat: compare BaZi compatibility"
```

### Task 9: Add the compatibility reading

**Files:**
- Modify: `plugins/chinese-metaphysics/skills/bazi-compatibility-reading/SKILL.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-compatibility-reading/agents/openai.yaml`
- Create: `plugins/chinese-metaphysics/skills/bazi-compatibility-reading/references/output-template.md`
- Create: `plugins/chinese-metaphysics/skills/bazi-compatibility-reading/references/examples.md`
- Create: `evals/bazi-compatibility-reading/evals.json`

**Interfaces:**
- Consumes: validated compatibility JSON, its verified rendering, or complete equivalent pasted data.
- Produces: `bazi_compatibility_reading_<name-a>_<name-b>.md` with the eleven approved sections.

- [ ] **Step 1: Write RED routing and behavior evaluations**

Cover calculator hand-off, direct file reading, complete pasted data, a general relationship, each explicit relationship type, weak contextual evidence, asymmetric directional support, alternate-chart sensitivity, corrupt data, raw two-person details routing back to the calculator, and prohibited probability language.

- [ ] **Step 2: Implement validation and evidence weighting instructions**

Require two verified source identities, all five dimensions, their ledgers and weights, general score, optional contextual score, confidence, and sensitivity. Preserve directional ownership. Never recompute a chart, invent a relationship type, or turn a score into a probability.

- [ ] **Step 3: Add bilingual template and examples**

Provide the fixed sections for basis, scorecard, complement/drain, asymmetry, affinity, communication, conflict/repair, stability/boundaries, selected context, synthesis/actions, and evidence index. Demonstrate a high-affinity/low-stability result without flattening it into one verdict.

- [ ] **Step 4: Verify and commit**

```bash
python3 scripts/run-evals.py --check
python3 -m unittest tests.bazi_skill.test_skill_contract -v
git add plugins/chinese-metaphysics/skills/bazi-compatibility-reading evals/bazi-compatibility-reading
git commit -m "feat: add BaZi compatibility readings"
```

### Task 10: Finish publication copy and full verification

**Files:**
- Modify: `plugins/chinese-metaphysics/skills/README.md`
- Modify: `plugins/chinese-metaphysics/.claude-plugin/plugin.json`
- Modify: `plugins/chinese-metaphysics/plugin.json`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `skills.sh.json`
- Modify: `.version-bump.json` if new contract tests carry the repository version
- Verify: every file changed by Tasks 1–9

**Interfaces:**
- Consumes: all implemented calculators, reading contracts, tests, and evals.
- Produces: a release-ready, installable, self-contained plugin with synchronized registries and vendored shared content.

- [ ] **Step 1: Replace every remaining scaffold marker**

Run:

```bash
rg -n "PLACEHOLDER|TBD|TODO|FIXME" plugins/chinese-metaphysics evals/bazi-* README.md README.zh-CN.md skills.sh.json
```

Expected: no matches.

- [ ] **Step 2: Synchronize shared files and audit descriptions**

```bash
python3 scripts/sync-shared.py
python3 scripts/sync-shared.py --check
python3 scripts/check-descriptions.py --report
python3 scripts/run-evals.py --check
```

Expected: all commands exit 0; the four descriptions remain distinct and state both trigger and exclusion boundaries.

- [ ] **Step 3: Run the complete test and repository suite**

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate-repository.py
python3 scripts/bump-version.py --audit
python3 scripts/ci-pins.py check
uvx ruff check .
uvx ruff format --check .
shellcheck scripts/*.sh
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 4: Run the real Swiss integration path**

```bash
uv run --with pyswisseph python3 -m unittest tests.bazi_skill.test_calendar tests.bazi_skill.test_compute_chart -v
```

Expected: official fixtures, chart generation, and boundary tests pass with the actual runtime dependency.

- [ ] **Step 5: Package and inspect every new skill**

```bash
BAZI_ARCHIVES=$(mktemp -d)
BAZI_UNPACKED=$(mktemp -d)
python3 scripts/package-skill.py plugins/chinese-metaphysics/skills/bazi-chart "$BAZI_ARCHIVES"
python3 scripts/package-skill.py plugins/chinese-metaphysics/skills/bazi-reading "$BAZI_ARCHIVES"
python3 scripts/package-skill.py plugins/chinese-metaphysics/skills/bazi-compatibility "$BAZI_ARCHIVES"
python3 scripts/package-skill.py plugins/chinese-metaphysics/skills/bazi-compatibility-reading "$BAZI_ARCHIVES"
for archive in "$BAZI_ARCHIVES"/*.skill; do
  python3 -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
    "$archive" "$BAZI_UNPACKED"
done
python3 scripts/verify-install.py "$BAZI_UNPACKED" \
  --expect bazi-chart --expect bazi-reading --expect bazi-compatibility --expect bazi-compatibility-reading
```

Expected: every archive is self-contained and contains synchronized `shared/` content.

- [ ] **Step 6: Review the final diff against the approved design**

Verify each spec section maps to code, tests, evals, or explicit skill instructions. Confirm no forecasting, no hard-coded person, no organization-specific content, no Markdown parsing as a machine interface, and no unrelated repository changes.

- [ ] **Step 7: Commit the release-ready surface**

```bash
git add .claude-plugin/marketplace.json .coveragerc .version-bump.json \
  README.md README.zh-CN.md bundle/.claude-plugin/plugin.json \
  plugins/chinese-metaphysics evals/bazi-chart evals/bazi-reading \
  evals/bazi-compatibility evals/bazi-compatibility-reading \
  scripts/validate-repository.py skills.sh.json tests/bazi_skill
git commit -m "feat: publish BaZi skill suite"
```

If the working tree is already clean because earlier task commits captured every file, do not create an empty commit.
