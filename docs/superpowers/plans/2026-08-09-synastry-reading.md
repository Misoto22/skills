# Synastry Reading Framework Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the four hard-coded relationship categories in `synastry-reading` with a fixed relationship-mechanism core and evidence-selected real-life domains.

**Architecture:** Keep the existing calculator, automatic hand-off, source validation, evidence ledger, and Markdown artifact contract unchanged. Revise only the prose analysis layer: every report uses the same mechanism-first core, while requested or strongly supported life domains are selected under an explicit evidence threshold.

**Tech Stack:** Agent Skills Markdown, YAML client metadata, JSON evaluation suites, Python `unittest` contract tests, repository validation scripts.

## Global Constraints

- The raw `synastry_<name-a>_<name-b>.txt` file remains data only.
- `synastry-reading` adds no Python or third-party runtime dependency.
- The reading output remains `synastry_reading_<name-a>_<name-b>.md` beside the source unless another output directory is requested.
- Every report contains all fixed relationship-mechanism sections in the defined order.
- Requested real-life domains are included; unrequested domains require two independent major indicators or one tight personal/angle contact plus a relevant directional overlay.
- Weak evidence is disclosed instead of being replaced with generic astrology.
- Every substantive interpretation cites measured aspects with orbs or directional house overlays.
- The reading does not infer the relationship label, recompute the chart, invent evidence, predict events, or assign a compatibility score.
- Runtime content remains organization-neutral and contains no local absolute path.
- All code identifiers, comments, documentation, and commit messages are English.

---

### Task 1: Lock the revised reading contract with failing tests

**Files:**
- Modify: `tests/synastry_skill/test_skill_contract.py`
- Modify: `evals/synastry-reading/evals.json`

**Interfaces:**
- Consumes: the published `synastry-reading` skill and its Markdown template.
- Produces: an executable contract for the fixed mechanism headings and a declarative contract for adaptive applied domains.

- [ ] **Step 1: Add the failing template contract**

Add paths for the reading skill and template, then add this test:

```python
READING_SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry-reading"
READING_SKILL_PATH = READING_SKILL / "SKILL.md"
READING_TEMPLATE_PATH = READING_SKILL / "references" / "output-template.md"

def test_reading_template_uses_mechanisms_before_applied_domains(self) -> None:
    text = READING_TEMPLATE_PATH.read_text(encoding="utf-8")
    headings = (
        "## Relationship signature",
        "## Reciprocity and asymmetry",
        "## Emotional bond and security",
        "## Attraction, romance, and intimacy",
        "## Communication and mental rhythm",
        "## Conflict, power, and repair",
        "## Trust, boundaries, and commitment",
        "## Growth, values, and shared direction",
        "## Applied life domains",
        "## Overall synthesis",
        "## Evidence index",
    )
    positions = [text.index(heading) for heading in headings]
    self.assertEqual(positions, sorted(positions))
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python3 -m unittest tests.synastry_skill.test_skill_contract.SkillContractTests.test_reading_template_uses_mechanisms_before_applied_domains -v`

Expected: `ERROR` at `text.index("## Relationship signature")` because the old template still starts with the four example categories.

- [ ] **Step 3: Revise the evaluation expectations before production content**

Replace fixed-category expectations with assertions that:

- all mechanism-first core sections are present in order
- requested domains appear even when the report must disclose weak evidence
- unrequested domains appear only after the evidence threshold is met
- the report distinguishes directional and asymmetric effects
- generic filler and inferred relationship labels are prohibited

Add one behavior case whose request asks only about domestic life and money, and one general reading case where only strongly activated life domains should be selected.

- [ ] **Step 4: Validate the evaluation JSON**

Run: `python3 -m json.tool evals/synastry-reading/evals.json >/dev/null`

Expected: exit code 0.

### Task 2: Implement the hybrid analysis framework

**Files:**
- Modify: `plugins/astrology/skills/synastry-reading/SKILL.md`
- Modify: `plugins/astrology/skills/synastry-reading/references/output-template.md`
- Modify: `plugins/astrology/skills/synastry-reading/references/examples.md`
- Modify: `plugins/astrology/skills/synastry-reading/agents/openai.yaml`

**Interfaces:**
- Consumes: a complete synastry measurement file and optional user-requested topics.
- Produces: one evidence-linked Markdown report with a fixed core plus selected applied-domain modules.

- [ ] **Step 1: Replace the four-category routing table**

Define evidence routes for the fixed core: relationship signature; reciprocity and asymmetry; emotional security; attraction and intimacy; communication; conflict, power, and repair; trust, boundaries, and commitment; growth, values, and shared direction.

- [ ] **Step 2: Add the applied-domain selection rule**

Include every explicitly requested domain. Include an unrequested domain only with either two independent major indicators or one tight personal/angle contact plus a relevant directional house overlay. Keep requested weak-evidence sections and label the evidence limit; omit unsupported unrequested domains.

- [ ] **Step 3: Replace both language templates**

Write the English and Chinese fixed headings from the approved design. Put `Evidence`/`星盘证据` inside every fixed section and selected domain. Give the adaptive section repeatable module placeholders without hard-coding friendship, career, or money as mandatory output.

- [ ] **Step 4: Revise examples and client metadata**

Show one relationship-mechanism excerpt, one evidence-qualified applied domain, one requested weak-evidence domain, and the unchanged incomplete-source refusal. Change client copy from “fixed report” to “structured, evidence-linked report.”

- [ ] **Step 5: Run the focused test and verify GREEN**

Run: `python3 -m unittest tests.synastry_skill.test_skill_contract.SkillContractTests.test_reading_template_uses_mechanisms_before_applied_domains -v`

Expected: one test passes.

- [ ] **Step 6: Run the complete focused suite**

Run: `python3 -m unittest discover -s tests/synastry_skill -t tests -v`

Expected: all synastry tests pass.

### Task 3: Remove stale four-category publication copy

**Files:**
- Modify if matched: `README.md`
- Modify if matched: `README.zh-CN.md`
- Modify if matched: `plugins/astrology/plugin.json`
- Modify if matched: `plugins/astrology/.claude-plugin/plugin.json`
- Modify if matched: `plugins/astrology/skills/README.md`

**Interfaces:**
- Consumes: the published hybrid reading behavior.
- Produces: marketplace and repository descriptions that accurately describe mechanism-first analysis.

- [ ] **Step 1: Find stale promises**

Run: `rg -n "love, friendship, business partnership, and money|爱情、友情、事业合作和金钱|four relationship dimensions|四个维度" README.md README.zh-CN.md plugins/astrology evals/synastry-reading`

Expected: only files that still describe the old mandatory shape are listed.

- [ ] **Step 2: Replace stale publication copy**

Describe the output as a structured, evidence-linked reading with a fixed relationship-mechanism core and evidence-selected real-life domains. Keep manifest descriptions synchronized where their shared fields must match.

- [ ] **Step 3: Run metadata checks**

Run:

```bash
python3 scripts/run-evals.py --check
python3 scripts/check-descriptions.py --report
```

Expected: all evaluation suites and descriptions pass.

### Task 4: Verify and update the existing pull request

**Files:**
- Verify: all changed files from Tasks 1-3
- Update: Git branch `codex/add-synastry-reading` and Draft PR #36

**Interfaces:**
- Consumes: the complete revised implementation.
- Produces: a clean pushed branch and an updated Draft PR describing the hybrid framework.

- [ ] **Step 1: Run repository verification**

Run:

```bash
python3 scripts/validate-repository.py
python3 scripts/run-evals.py --check
python3 scripts/check-descriptions.py --report
uvx ruff check .
uvx ruff format --check .
shellcheck scripts/*.sh
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 2: Review requirements and scope**

Read the approved design beside the final diff. Confirm every fixed section, selection threshold, weak-evidence behavior, asymmetry rule, evidence citation rule, and prohibited inference is represented. Confirm calculator scripts are unchanged and no unrelated files changed.

- [ ] **Step 3: Commit and push**

Stage only the planned files, commit with `feat: broaden synastry reading framework`, and push `codex/add-synastry-reading` without force.

- [ ] **Step 4: Update and verify PR #36**

Update its body to explain the fixed mechanism core and evidence-selected domains. Verify the PR remains open and draft, points from `codex/add-synastry-reading` to `main`, and includes the new commit.
