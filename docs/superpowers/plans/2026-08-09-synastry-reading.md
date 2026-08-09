# Synastry Reading Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a `synastry-reading` skill in the existing `astrology` plugin and make a successful `synastry` calculation hand its raw data file to that skill automatically.

**Architecture:** Keep the existing Python calculator and its `.txt` artifact unchanged as the measurement layer. Add a prose-only reading skill that validates the calculator artifact, interprets only cited measurements, and writes a fixed Markdown report; the calculator's instructions own the automatic hand-off.

**Tech Stack:** Agent Skills Markdown, YAML client metadata, JSON evaluation suites, repository Python validation scripts, GitHub pull request workflow.

## Global Constraints

- The raw `synastry_<name-a>_<name-b>.txt` file remains data only.
- `synastry-reading` adds no Python or third-party dependency.
- The reading output is `synastry_reading_<name-a>_<name-b>.md` beside the source unless another output directory is requested.
- The reading always covers love, friendship, business partnership, and money in the fixed order.
- Every substantive interpretation cites measured aspects with orbs or directional house overlays.
- The reading does not recompute the chart, invent evidence, predict events, or assign a compatibility score.
- Runtime content remains organization-neutral and contains no local absolute path.
- All code identifiers, comments, documentation, and commit messages are English.

---

### Task 1: Define routing and behavior evaluations

**Files:**
- Create: `evals/synastry-reading/evals.json`
- Modify: `evals/synastry/evals.json`

**Interfaces:**
- Consumes: the existing evaluation schema used by `scripts/run-evals.py`.
- Produces: routing cases for `synastry-reading` and behavioral assertions for the automatic calculator hand-off and fixed reading output.

- [ ] **Step 1: Add the failing evaluation suite before publishing the skill**

Create a suite with at least these trigger boundaries:

```json
{
  "skill": "synastry-reading",
  "triggers": [
    {
      "id": "existing-file",
      "prompt": "Read the attached synastry_Person-A_Person-B.txt and interpret the relationship.",
      "expected": "Uses the existing measurements and writes the fixed Markdown reading."
    }
  ],
  "non_triggers": [
    {
      "id": "raw-birth-details",
      "prompt": "Run a synastry for two supplied birth records.",
      "routes_to": "synastry",
      "expected": "Calculation belongs to synastry."
    }
  ],
  "behaviors": []
}
```

Expand this to cover Chinese interpretation phrasing, a calculator hand-off, a single natal chart, transits, incomplete source data, all four report dimensions, evidence citations, degraded ephemeris coverage, and prohibited scores or predictions.

- [ ] **Step 2: Run the evaluation contract and verify RED**

Run: `python3 scripts/run-evals.py --check`

Expected: failure because `synastry-reading` is not yet a published skill.

- [ ] **Step 3: Update the existing calculator behavior expectation**

Replace the old "stop at data" expectation with assertions that the raw file remains uninterpreted and the workflow immediately invokes `synastry-reading` after a successful write.

- [ ] **Step 4: Validate the JSON syntax independently**

Run: `python3 -m json.tool evals/synastry-reading/evals.json >/dev/null && python3 -m json.tool evals/synastry/evals.json >/dev/null`

Expected: exit code 0.

### Task 2: Scaffold and author the reading skill

**Files:**
- Create through scaffold: `plugins/astrology/skills/synastry-reading/SKILL.md`
- Create through scaffold: `plugins/astrology/skills/synastry-reading/agents/openai.yaml`
- Create: `plugins/astrology/skills/synastry-reading/references/output-template.md`
- Create: `plugins/astrology/skills/synastry-reading/references/examples.md`
- Modify through scaffold: `.claude-plugin/marketplace.json`
- Modify through scaffold: `.version-bump.json`
- Modify through scaffold: `README.md`
- Modify through scaffold: `README.zh-CN.md`
- Modify through scaffold: `bundle/.claude-plugin/plugin.json`
- Modify through scaffold: `plugins/astrology/.claude-plugin/plugin.json`
- Modify through scaffold: `plugins/astrology/skills/README.md`
- Modify through scaffold: `scripts/validate-repository.py`
- Modify through scaffold: `skills.sh.json`

**Interfaces:**
- Consumes: a `synastry_*.txt` path or equivalent complete pasted data.
- Produces: `synastry_reading_<name-a>_<name-b>.md` following `references/output-template.md`.

- [ ] **Step 1: Run the repository scaffold**

Run: `python3 scripts/new-skill.py astrology synastry-reading`

Expected: the skill directory and all repository registrations are created, with authoring placeholders reported by the command.

- [ ] **Step 2: Replace every scaffold placeholder with final metadata**

Use a discovery description that triggers on an existing synastry data file, a request to interpret or analyze one, or the automatic hand-off from `synastry`; explicitly exclude birth-data calculation, natal charts, transits, and forecasts.

Set `agents/openai.yaml` to:

```yaml
interface:
  display_name: "Synastry Reading"
  short_description: "Interpret an existing two-person synastry file"
  default_prompt: "Use $synastry-reading to interpret an existing synastry data file and write the fixed, evidence-linked Markdown report."
policy:
  allow_implicit_invocation: true
```

- [ ] **Step 3: Author the executable reading workflow**

The skill body must:

1. Validate both natal blocks, the aspect table with orbs, and both overlay directions.
2. Stop and name a missing required section rather than writing a partial report.
3. Prioritize tight personal-planet and angle Ptolemaic aspects, then repeated themes and overlays.
4. Treat outer planets, nodes, asteroids, lots, and minor aspects as supporting evidence.
5. Cite every substantive interpretation and repeat source limitations.
6. Write the Markdown report through the fixed template.
7. Return the source and output paths with a short neutral overview.

- [ ] **Step 4: Add the fixed template and worked examples**

`output-template.md` carries the complete English and Chinese heading contracts. `examples.md` covers a direct English reading, an automatic Chinese hand-off, a source missing optional asteroid data, and a refusal on incomplete synastry data.

- [ ] **Step 5: Run the evaluation contract and verify GREEN**

Run: `python3 scripts/run-evals.py --check`

Expected: `evaluation suites are complete` with exit code 0.

- [ ] **Step 6: Run description validation**

Run: `python3 scripts/check-descriptions.py --report`

Expected: every description passes length, negative-boundary, placeholder, and overlap checks.

### Task 3: Connect the calculator hand-off and verify publication

**Files:**
- Modify: `plugins/astrology/skills/synastry/SKILL.md`
- Modify: `plugins/astrology/skills/synastry/references/examples.md`
- Modify: `plugins/astrology/skills/README.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

**Interfaces:**
- Consumes: the successful calculator output path.
- Produces: an immediate invocation of `synastry-reading` with the exact path, while preserving the raw data artifact.

- [ ] **Step 1: Change the calculator reporting contract**

Replace the current instruction to stop after listing measurements with this sequence:

```text
After the data file exists, invoke synastry-reading immediately with that exact path.
Do not wait for another user request. Do not add interpretation to the data file.
If calculation failed, do not invoke the reading skill.
```

- [ ] **Step 2: Update the worked examples**

Show both output paths on successful English and Chinese runs. Preserve the refusal case and ensure it produces neither a data file nor a reading file.

- [ ] **Step 3: Review generated registry copy**

Replace the scaffold's README placeholders with concise English and Chinese descriptions, confirm both astrology plugin manifests list both skills in sorted order, and confirm all root registries name `synastry-reading` once.

- [ ] **Step 4: Run focused checks**

Run:

```bash
python3 scripts/run-evals.py --check
python3 -m unittest discover -s tests/synastry_skill -t tests -v
python3 scripts/validate-repository.py
```

Expected: every command exits 0.

- [ ] **Step 5: Run release-quality checks**

Run:

```bash
uvx ruff check .
uvx ruff format --check .
shellcheck scripts/*.sh
git diff --check
```

Expected: every command exits 0 without warnings requiring source changes.

- [ ] **Step 6: Review the final diff against the design**

Confirm every acceptance criterion in `docs/superpowers/specs/2026-08-09-synastry-reading-design.md`, scan for runtime absolute paths and placeholders, and verify no unrelated file changed.

- [ ] **Step 7: Publish the branch**

Stage only the planned files, commit with a terse conventional message, push `codex/add-synastry-reading`, and open a draft pull request against `main` with the changes, rationale, impact, and validation commands.
