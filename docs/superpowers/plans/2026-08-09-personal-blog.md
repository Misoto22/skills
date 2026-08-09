# Personal Blog Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish `/writing:personal-blog`, a five-mode, evidence-safe long-form writing skill that preserves an author's supplied voice and returns finished articles as raw Markdown.

**Architecture:** Keep routing and the end-to-end contract in `SKILL.md`, with mode recipes and voice analysis in two directly linked references. Reuse the writing plugin's shared tone and format rules after explicitly scoping their message-only clauses, and use repository eval cases as the behavioral test surface.

**Tech Stack:** Agent Skills Markdown, YAML, JSON evaluation fixtures, dependency-free repository validation scripts.

## Global Constraints

- Publish inside the existing `writing` plugin as `/writing:personal-blog`.
- Keep all runtime content organization-neutral and free of personal identity, credentials, and local absolute paths.
- Never invent a writer's experience, memory, belief, emotion, quotation, result, source, or citation.
- Support `explainer`, `idea-essay`, `personal-essay`, `review`, and `technical` modes.
- Return finished articles as raw Markdown unless the user asks for another artefact.
- Do not require a hook, three-part body, recap, or call to action.
- Use dependency-free prose and evaluation fixtures; add no runtime script or asset.
- Run the repository scaffold and shared-file sync instead of registering or copying files by hand.

---

### Task 1: Behavioral Baseline and Published Scaffold

**Files:**
- Create: `evals/personal-blog/evals.json`
- Create: `evals/personal-blog/iteration-1/baseline-summary.md`
- Create through scaffold: `plugins/writing/skills/personal-blog/SKILL.md`
- Create through scaffold: `plugins/writing/skills/personal-blog/agents/openai.yaml`
- Modify through scaffold: `.claude-plugin/marketplace.json`
- Modify through scaffold: `.version-bump.json`
- Modify through scaffold: `README.md`
- Modify through scaffold: `README.zh-CN.md`
- Modify through scaffold: `plugins/writing/.claude-plugin/plugin.json`
- Modify through scaffold: `plugins/writing/skills/README.md`
- Modify through scaffold: `scripts/validate-repository.py`
- Modify through scaffold: `skills.sh.json`

**Interfaces:**
- Consumes: approved design in `docs/superpowers/specs/2026-08-09-personal-blog-design.md`.
- Produces: registered `personal-blog` skill shell and a reusable evaluation contract with at least five triggers, five non-triggers, and behavior cases for evidence, voice, mode structure, and raw Markdown.

- [ ] **Step 1: Run baseline prompts without the skill**

Use fresh agents on representative requests for an idea essay, a sparse personal essay, a sourced technical article, and a draft edit. Record whether they impose a generic hook/body/CTA structure, fabricate personal material, treat “preserve voice” abstractly, or wrap Markdown in commentary.

- [ ] **Step 2: Record the observed failures**

Write only observed baseline behavior and verbatim excerpts to `evals/personal-blog/iteration-1/baseline-summary.md`; do not write hypothetical failures.

- [ ] **Step 3: Write the evaluation contract**

Create `evals/personal-blog/evals.json` with this top-level shape:

```json
{
  "skill": "personal-blog",
  "triggers": [],
  "non_triggers": [],
  "behaviors": []
}
```

Populate it with all five modes, Chinese and English prompts, sparse-source and voice-sample cases, technical verification, raw Markdown delivery, and explicit neighboring routes to `email`, `tempering`, and `readme` where applicable.

- [ ] **Step 4: Scaffold the registered skill**

Run:

```bash
python3 scripts/new-skill.py writing personal-blog
```

Expected: the skill shell and all mechanical registry changes are created; repository validation still fails because scaffold markers remain.

- [ ] **Step 5: Verify the RED state**

Run:

```bash
python3 scripts/check-descriptions.py
python3 scripts/validate-repository.py
```

Expected: failure names the unfinished `personal-blog` description or body, proving the unpublished scaffold is not release-ready.

---

### Task 2: Minimal Skill, References, and Shared-Rule Scoping

**Files:**
- Modify: `plugins/writing/skills/personal-blog/SKILL.md`
- Create: `plugins/writing/skills/personal-blog/references/modes.md`
- Create: `plugins/writing/skills/personal-blog/references/voice.md`
- Modify: `plugins/writing/skills/personal-blog/agents/openai.yaml`
- Modify: `plugins/writing/shared/tone.md`
- Modify: `plugins/writing/shared/format.md`
- Generate: `plugins/writing/skills/*/shared/tone.md`
- Generate: `plugins/writing/skills/*/shared/format.md`

**Interfaces:**
- Consumes: evaluation failures and registered scaffold from Task 1.
- Produces: a self-contained skill whose references resolve inside every installer and whose shared rules remain valid for messages and long-form prose.

- [ ] **Step 1: Write the minimal routing and workflow contract**

Replace the scaffold with an imperative `SKILL.md` that selects a primary mode, builds only the requested artefact, separates personal material from verifiable claims, loads the relevant direct reference, preserves the writer's evidence and voice, and returns a finished article as raw Markdown.

- [ ] **Step 2: Write mode recipes**

Add `references/modes.md` with a compact table for mode selection followed by distinct structure and integrity checks for all five modes. Each recipe must state what evidence can support it and what generic article pattern to avoid.

- [ ] **Step 3: Write the voice profile contract**

Add `references/voice.md` with observable profile fields, an evidence hierarchy, visible bracketed gaps, AI-prose warning signs, and one before/after example that removes invented autobiography while preserving the argument.

- [ ] **Step 4: Scope shared rules**

In `plugins/writing/shared/tone.md`, limit the 1.5× rewrite ratio and apology guidance to messages while retaining fact preservation and anti-filler rules for all prose. In `plugins/writing/shared/format.md`, limit channel shape and final-request rules to messages while retaining language matching and meaningful structure for all prose.

- [ ] **Step 5: Vendor shared files**

Run:

```bash
python3 scripts/sync-shared.py
```

Expected: all three writing skills carry byte-identical copies of both shared files.

- [ ] **Step 6: Replace generated metadata and registry prose**

Set `agents/openai.yaml` to a concise display name, a 25–64 character description, a `$personal-blog` default prompt, and implicit invocation. Replace every unfinished registry line with English canonical prose and a faithful Chinese README translation.

- [ ] **Step 7: Verify the GREEN state**

Run:

```bash
python3 scripts/check-descriptions.py --report
python3 scripts/run-evals.py --check
python3 scripts/validate-repository.py
```

Expected: all three commands exit zero.

---

### Task 3: Forward Test, Refine, and Ship

**Files:**
- Modify if required: `plugins/writing/skills/personal-blog/SKILL.md`
- Modify if required: `plugins/writing/skills/personal-blog/references/modes.md`
- Modify if required: `plugins/writing/skills/personal-blog/references/voice.md`
- Modify if required: `evals/personal-blog/evals.json`
- Modify if required: `evals/personal-blog/iteration-1/baseline-summary.md`

**Interfaces:**
- Consumes: the release-ready skill from Task 2.
- Produces: independently exercised behavior, complete repository checks, reviewed commits, a pushed branch, and a GitHub pull request.

- [ ] **Step 1: Forward-test with the installed skill content**

Run fresh agents on the same four baseline requests while exposing the completed skill. Check the raw outputs against the eval expectations rather than against an intended model answer.

- [ ] **Step 2: Close observed gaps**

If an agent still fabricates personal content, forces a generic structure, invents a citation, erases voice, or wraps the requested Markdown, tighten the smallest relevant positive contract and repeat that scenario.

- [ ] **Step 3: Run the full release gate**

Run:

```bash
uvx ruff check .
uvx ruff format --check .
shellcheck scripts/*.sh
python3 scripts/bump-version.py --audit
python3 scripts/ci-pins.py check
python3 scripts/check-descriptions.py
python3 scripts/run-evals.py --check
python3 scripts/validate-repository.py
git diff --check
```

Expected: every command exits zero without warnings attributable to this change.

- [ ] **Step 4: Review the complete branch diff**

Compare the branch to `origin/main`; verify that all changes belong to the skill, registry, shared scoping, evals, and design documents, and that no secret, local path, generated cache, or unrelated user change is present.

- [ ] **Step 5: Commit implementation**

Commit with an English imperative subject under 72 characters and a `Co-Authored-By: Codex <noreply@openai.com>` trailer.

- [ ] **Step 6: Push and open a pull request**

Push `codex/add-personal-blog-skill` to `origin`, open a ready pull request against `main`, and include the behavior contract and exact verification commands in the PR body.
