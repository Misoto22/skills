# BaZi Reader and Evidence Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the default BaZi natal and compatibility reports readable without weakening the separately stored audit trail.

**Architecture:** Keep calculation artifacts intact. Change the two reading-skill contracts so each writes a human reader report with a compact model data card and a sibling technical evidence artifact containing all machine-facing detail.

**Tech Stack:** Markdown skill instructions/templates/examples, JSON evaluations, dependency-free Python contract tests, existing repository validation scripts.

## Global Constraints

- Preserve calculator schemas, scores, validation, checksums, sensitivity handling, and prohibited-claim boundaries.
- Keep raw evidence IDs, exact values, checksums, model IDs, and arithmetic out of reader reports.
- Show rounded requested numbers only in reader data cards and label them as heuristic model references.
- Use display names, not stored left/right labels, in compatibility reader prose.

---

### Task 1: Lock the split-output contract with failing tests

**Files:**
- Modify: `tests/bazi_skill/test_skill_contract.py`
- Modify: `evals/bazi-reading/evals.json`
- Modify: `evals/bazi-compatibility-reading/evals.json`

- [ ] Add assertions requiring each reading skill to name its existing reader file, its sibling evidence file, a separate-evidence boundary, a `Model data card`, and no numbered markers in its reader template.
- [ ] Run `python3 -m unittest tests.bazi_skill.test_skill_contract -v` and confirm the new test fails because the current contracts still use a same-file technical appendix.
- [ ] Replace reader-first evaluation expectations with split-output requirements: no markers/raw IDs in reader prose; rounded model data card; separate evidence artifact with all exact trace data; selected-context priority and explicit directional naming for compatibility.

### Task 2: Replace the shared presentation contract

**Files:**
- Modify: `plugins/chinese-metaphysics/shared/report-presentation.md`

- [ ] Define reader-report language, data-card limits, one end-of-report evidence link, and prohibited machine detail.
- [ ] Define evidence-artifact contents and heading-based claim mapping.
- [ ] Remove compact-citation and final-appendix requirements.

### Task 3: Reshape the two reading skills

**Files:**
- Modify: `plugins/chinese-metaphysics/skills/bazi-reading/SKILL.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-reading/references/output-template.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-reading/references/examples.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-compatibility-reading/SKILL.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-compatibility-reading/references/output-template.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-compatibility-reading/references/examples.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-chart/SKILL.md`
- Modify: `plugins/chinese-metaphysics/skills/bazi-compatibility/SKILL.md`

- [ ] Update both reader skills to write the two named Markdown outputs after validation and to report both paths.
- [ ] Replace report orders with the human-question structures in the design.
- [ ] Place all source validation and exact ledger requirements in the evidence artifact; retain one compact reader data card.
- [ ] Update calculator hand-offs so they report reader and evidence paths after automatic interpretation.
- [ ] Rewrite examples to show natural Chinese prose without numbered citations.

### Task 4: Verify report artifacts and repository health

**Files:**
- Regenerate outside the repository: `bazi_reading_Henry.md`, `bazi_reading_evidence_Henry.md`, `bazi_compatibility_reading_Henry_Cindy.md`, `bazi_compatibility_evidence_Henry_Cindy.md`

- [ ] Run the contract test and confirm it passes.
- [ ] Regenerate both Henry/Cindy samples using the revised skills and verify the reader files contain no `〔`, raw IDs, checksums, model IDs, or exact arithmetic.
- [ ] Verify evidence files preserve all exact details, directional ownership, and selected-context arithmetic.
- [ ] Run `python3 scripts/sync-shared.py --check`, `python3 scripts/run-evals.py --check`, `python3 scripts/validate-repository.py`, `uvx ruff check .`, `uvx ruff format --check .`, `shellcheck scripts/*.sh`, and `python3 -m unittest discover -s tests -v`.

### Task 5: Release

**Files:**
- Modify through script: declared repository version files

- [ ] Bump the patch version with `python3 scripts/bump-version.py <next-version>`.
- [ ] Re-run version audit and full repository validation.
- [ ] Commit the validated implementation and release through the existing pull-request workflow.
