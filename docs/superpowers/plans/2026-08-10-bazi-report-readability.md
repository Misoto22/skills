# BaZi Report Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make BaZi natal and compatibility Markdown reports reader-first without weakening their verified audit trail.

**Architecture:** Keep all calculator artifacts and validation rules unchanged. Reshape the two prose-reading skills so the main report uses localized headings, compact numbered citations, rounded display values, and conclusion-first information hierarchy; move exact identifiers and arithmetic into a final technical appendix.

**Tech Stack:** Markdown skill instructions and templates, JSON evaluation suites, dependency-free repository validation scripts.

## Global Constraints

- Use the user's language throughout the reader-facing layer.
- Keep full checksums, model ids, exact arithmetic, unrounded values, and raw ledger ids in the final technical appendix only.
- Preserve source validation, alternate handling, heuristic disclaimers, and all prohibited deterministic claims.
- Do not alter calculation schemas, score algorithms, or source artifacts.

---

### Task 1: Add reader-first behavior cases

**Files:**
- Modify: `evals/bazi-reading/evals.json`
- Modify: `evals/bazi-compatibility-reading/evals.json`

**Interfaces:**
- Consumes: Existing `behaviors` arrays accepted by `scripts/run-evals.py --check`.
- Produces: Explicit expectations for conclusion-first layout, localization, compact citations, technical appendix placement, contextual-score priority, and named directional support.

- [ ] **Step 1: Add the natal readability case**

Add a `reader-first-chinese-report` behavior whose expectations require a Chinese-only main layer, conclusion before technical basis, `〔n〕` markers instead of raw ids, rounded display scores, and exact values in the final appendix.

- [ ] **Step 2: Add the compatibility readability case**

Add a `reader-first-chinese-report` behavior whose expectations require the selected relationship score first, Chinese scorecard labels, explicit `A → B` directions, no `left/right` in reader prose, and technical identifiers only in the appendix.

- [ ] **Step 3: Verify the baseline report fails the new contract**

Inspect `bazi_compatibility_reading_Henry_Cindy.md` and confirm it exposes raw checksum strings, English table headers, and raw evidence ids before the conclusion.

- [ ] **Step 4: Check evaluation JSON structure**

Run: `python3 scripts/run-evals.py --check`

Expected: exit 0; both new behavior cases are structurally valid.

### Task 2: Reshape the natal reading contract

**Files:**
- Modify: `plugins/chinese-metaphysics/skills/bazi-reading/SKILL.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-reading/references/output-template.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-reading/references/examples.md`

**Interfaces:**
- Consumes: Valid `chinese-metaphysics.bazi-chart` schema version 1 artifacts.
- Produces: One seven-section localized Markdown report with compact citations and a final audit appendix.

- [ ] **Step 1: Replace raw inline ids with compact citation markers**

Require sequential `〔1〕`, `〔2〕` markers in reader prose. Map each marker to exact raw ids and values in the final appendix.

- [ ] **Step 2: Replace the ten-section order**

Use: conclusion at a glance; chart overview; element and day-master summary; core structure; strengths and tensions; relationship, work, and reflection prompts; technical basis and evidence.

- [ ] **Step 3: Localize and round the reader layer**

Require one language per report, whole-number display scores and percentages, and exact unrounded values in the appendix.

- [ ] **Step 4: Update the example**

Show a concise Chinese opening with a conclusion block, a four-pillar table, and compact evidence markers; retain corrupt-source and alternate-boundary examples.

### Task 3: Reshape the compatibility reading contract

**Files:**
- Modify: `plugins/chinese-metaphysics/skills/bazi-compatibility-reading/SKILL.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-compatibility-reading/references/output-template.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-compatibility-reading/references/examples.md`

**Interfaces:**
- Consumes: Valid `chinese-metaphysics.bazi-compatibility` schema version 1 artifacts.
- Produces: One eight-section localized Markdown report with selected-context priority and named directional support.

- [ ] **Step 1: Establish the reader-first hierarchy**

Use: conclusion at a glance; two-chart overview; relationship scorecard; three core findings; each person's likely experience; strengths, friction, and repair; practical prompts; technical basis and evidence.

- [ ] **Step 2: Make direction unambiguous**

Require `Name A → Name B` in the reader layer and reserve stored `left/right` ownership for the appendix.

- [ ] **Step 3: Move calculation detail to the appendix**

Keep full source/comparison checksums, model id, exact five-dimensional values, weighted arithmetic, sensitivity variants, and raw ledger ids in section 8.

- [ ] **Step 4: Update mixed-dimension and asymmetry examples**

Use compact markers and concrete reader language while retaining non-blaming, non-deterministic interpretation.

### Task 4: Forward-test and validate

**Files:**
- Regenerate outside the repository: `bazi_reading_Henry.md`
- Regenerate outside the repository: `bazi_compatibility_reading_Henry_Cindy.md`

**Interfaces:**
- Consumes: The verified Henry, Cindy, and compatibility JSON artifacts from the real usage test.
- Produces: Reader-first sample reports matching the revised contracts.

- [ ] **Step 1: Forward-test the revised natal skill**

Generate the Henry report from the verified natal JSON and inspect section order, localization, rounded display values, citation markers, and appendix detail.

- [ ] **Step 2: Forward-test the revised compatibility skill**

Generate the Henry and Cindy romance report and confirm the romance score appears before the general score, directions use names, and no raw ids appear before section 8.

- [ ] **Step 3: Run repository checks**

Run:

```bash
python3 scripts/sync-shared.py --check
python3 scripts/run-evals.py --check
python3 scripts/validate-repository.py
uvx ruff check .
uvx ruff format --check .
shellcheck scripts/*.sh
python3 -m pytest
```

Expected: every command exits 0 with no validation, lint, formatting, shell, or unit-test failures.

### Task 5: Release the change

**Files:**
- Modify through script: every version declaration listed by `.version-bump.json`

**Interfaces:**
- Consumes: A validated reader-first report contract.
- Produces: The next patch release, a focused feature commit, a pushed branch, and a merged pull request.

- [ ] **Step 1: Bump the repository version**

Run: `python3 scripts/bump-version.py 0.8.$((1 + 1))`

Expected: all declared current-version occurrences become the next patch release with no drift.

- [ ] **Step 2: Re-run release validation**

Run: `python3 scripts/bump-version.py --audit && python3 scripts/validate-repository.py`

Expected: exit 0 and no undeclared version occurrences.

- [ ] **Step 3: Commit**

Stage only the design, plan, evaluation, reading-skill, template, example, and version files. Commit with `feat: improve BaZi report readability` and the configured co-author line.

- [ ] **Step 4: Push and merge**

Push a new `codex/` feature branch, open a ready pull request describing the reader-first output contract, wait for required checks, and merge without force-pushing.
