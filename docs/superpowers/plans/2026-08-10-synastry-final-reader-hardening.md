# Synastry Final Reader Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two residual final-review gaps in persisted reading recovery filenames and ledger-derived metadata evidence validation.

**Architecture:** Preserve the existing reader CLI and session state machine. Bind the canonical chart ID into durable commit metadata so live and recovered installs share the same filename invariant; replace punctuation heuristics for Basis metadata with exact values derived from the validated ledger.

**Tech Stack:** Dependency-free Python 3.11–3.13, `unittest`, existing Synastry v2 schema/ledger/session validators.

## Global Constraints

- Add behavioral tests and capture RED before production or skill edits.
- Persisted recovery must enforce the same exact basename as live installation: `synastry_reading_<validated-chart-id>.md`.
- Existing committing states without valid chart identity are malformed and follow bounded malformed-state cleanup; well-formed conflicts remain retryable.
- Every evidence-free Basis metadata line must match an exact normalized value derived from the validated ledger. No punctuation, conjunction, or translated separator may append interpretation.
- Exact supported limitation entries must be accepted, including values containing colons; any added interpretation requires direct paragraph evidence.
- Cover complete English and Chinese Basis blocks through executable validation.
- Keep public CLI/status/state names, schema version, JSON-only behavior, privacy, permissions, and licensing unchanged.
- Run full gates serially with `PYTHONDONTWRITEBYTECODE=1`; do not run paid providers or bump a version.

---

### Task 1: Bind persisted output identity and exact Basis metadata

**Files:**
- Modify: `plugins/astrology/skills/synastry-reading/scripts/reading_session.py`
- Modify: `plugins/astrology/skills/synastry-reading/scripts/validate_reading.py`
- Modify: `tests/synastry_reading_skill/test_reading_session_state_machine.py`
- Modify: `tests/synastry_reading_skill/test_validate_reading.py`
- Modify only if required by executable template behavior: `plugins/astrology/skills/synastry-reading/references/output-template.md`

**Interfaces:**
- Consumes: durable `commit.json`, `_commit_material()`, `_RecoveryResult`, `EvidenceLedger`, and Basis paragraph parsing.
- Produces: commit metadata containing validated `chart_id`; recovery-time exact basename enforcement; exact ledger-derived metadata entry validation in English and Chinese.

- [ ] **Step 1: Write and run persisted-recovery filename RED tests**

Create valid committing states whose destination basename is noncanonical, mismatched, traversal-shaped, or canonical. Prove current recovery installs the first three. Require noncanonical/mismatched states to classify malformed, retain before the fallback deadline, and be atomically removed after it; require the canonical state to recover successfully. Also prove live commit manifests persist the ledger chart ID.

- [ ] **Step 2: Implement durable chart-ID binding**

Persist `chart_id` in `commit.json`. Validate it as exactly twelve lowercase hexadecimal characters in `_commit_material()`, and require:

```python
target.name == f"synastry_reading_{chart_id}.md"
```

before installation. Do not derive trust from the filename itself. Preserve existing manifest privacy and retryable conflict behavior.

- [ ] **Step 3: Write and run complete Basis-block RED tests**

Build representative English and Chinese Basis blocks from a real `EvidenceLedger`. Include exact Source, profile/configuration, provenance/backend, and every limitation line. Require exact blocks to pass. Add uncited append variants using comma/fullwidth comma, `and`/Chinese conjunctions, semicolon, colon, dash, and newline continuation; require each to fail. Include a legitimate limitation whose text contains a colon and require it to pass exactly.

- [ ] **Step 4: Implement exact ledger-derived metadata validation**

Generate the finite accepted normalized metadata entries from the ledger/configuration/provenance/limitations and the selected language. Treat an evidence-free paragraph as structural only when it equals one accepted entry. Remove punctuation-boundary heuristics. If a paragraph is not exact, validate it as a substantive paragraph with direct evidence. Keep Source forms ledger-bound and preserve inline-code/quote/comment protections.

- [ ] **Step 5: Verify focused and full GREEN**

Run sequentially in the pinned supported environment:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest \
  tests.synastry_reading_skill.test_reading_session_state_machine \
  tests.synastry_reading_skill.test_validate_reading -v
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python scripts/validate-repository.py
python3 scripts/run-evals.py --check
python3 scripts/check-descriptions.py --report
python3 scripts/sync-shared.py --check
python3 scripts/bump-version.py --audit
uvx ruff check .
uvx ruff format --check .
shellcheck scripts/*.sh
git diff --check
```

- [ ] **Step 6: Commit**

```bash
git add plugins/astrology/skills/synastry-reading tests/synastry_reading_skill
git commit -m "fix: bind recovered synastry readings"
```
