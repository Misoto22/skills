# Synastry Session Durability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make synastry-reading finalization refuse special destinations, persist published directory entries before consuming recovery state, bound corrupt-state retention, and isolate unsafe recovery entries.

**Architecture:** Keep the existing session state machine and public CLI unchanged. Deepen the atomic-write module so publication includes destination-directory durability, and centralize final-destination normalization in one no-follow helper used by live finalization and persisted recovery.

**Tech Stack:** Dependency-free Python 3.11–3.13, `unittest`, POSIX file operations, existing Synastry v2 reader validators.

## Global Constraints

- Follow `docs/superpowers/specs/2026-08-10-synastry-session-durability-design.md` exactly.
- Add tests before production edits and record the failing output.
- Keep all public JSON schemas, commands, status shapes, and skill names unchanged.
- Never follow or overwrite a final destination symlink or special entry; retain `.committing-<token>` on refusal.
- Delete committing recovery material only after parent-directory durability and stable exact-byte readback both succeed.
- Bound malformed-state retention to `MAX_TTL_SECONDS + _CLOCK_GRACE_SECONDS` from the current observation even when `st_mtime` is in the future.
- A malformed or unsafe committing state must not abort sweeping of other states or prevent an unrelated session from starting.
- Use dependency-free Python and preserve organization neutrality, JSON-only runtime content, `0600` files, and `0700` private directories.
- Run full repository checks serially because contract fixtures temporarily mutate repository registries.

---

### Task 1: Harden destination publication and recovery

**Files:**
- Modify: `plugins/astrology/skills/synastry-reading/scripts/reading_session.py`
- Modify: `plugins/astrology/skills/synastry-reading/scripts/validate_synastry.py`
- Modify: `tests/synastry_reading_skill/test_reading_session_state_machine.py`
- Modify: `tests/synastry_reading_skill/test_validate_synastry.py`

**Interfaces:**
- Consumes: `_write_atomic_bytes(...) -> Path`, `_recover_committing(root, committing) -> bool`, `_sweep_expired(root) -> None`, and the existing staging/public/finalizing/cancelling/committing state layout.
- Produces: `_absolute_output_path(path, root) -> Path` (or an equivalently small internal helper) that preserves the final path component while validating its parent; atomic writes whose success includes `fsync(destination.parent)`; bounded fallback deadlines; per-entry recovery failure isolation.

- [ ] **Step 1: Add failing destination-path behavior tests**

Add real CLI/state-machine tests that create a private session and attempt finalization to:

```text
output-link.md -> absent-target.md
output-link.md -> exact-existing-target.md
loop-a -> loop-b -> loop-a, with the persisted destination below loop-a
```

Assert both final symlink cases exit nonzero, do not create or change the target, and retain `.committing-<token>`. Assert a stale committing state containing the symlink-loop destination makes `_recover_committing` return `False`; a subsequent unrelated `start` still succeeds and leaves the unsafe committing state intact.

- [ ] **Step 2: Add failing durability and expiry behavior tests**

Add a narrow filesystem-boundary test around `_write_atomic_bytes` that distinguishes the prepared-file `fsync` from an opened parent-directory `fsync`, records ordering, and proves the call returns only after the directory sync. Add a failure case where parent-directory `fsync` raises after publication: exact output may exist, but session finalization must exit nonzero and retain `.committing-<token>` for idempotent recovery.

Add a malformed hidden-state test that sets `st_mtime` far in the future, evaluates the fallback with a controlled current time, and asserts its deadline is no later than:

```python
now + MAX_TTL_SECONDS + _CLOCK_GRACE_SECONDS
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run in the supported pinned Python environment:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest \
  tests.synastry_reading_skill.test_reading_session_state_machine \
  tests.synastry_reading_skill.test_validate_synastry -v
```

Expected: the new tests fail because final symlinks are dereferenced, destination parents are not synced, future `mtime` is unbounded, and a symlink-loop recovery exception escapes sweeping.

- [ ] **Step 4: Implement no-follow destination normalization**

Replace final-component `resolve(strict=False)` calls with one internal helper that:

```python
expanded = path.expanduser()
absolute = expanded if expanded.is_absolute() else Path.cwd() / expanded
resolved_parent = absolute.parent.resolve(strict=False)
candidate = resolved_parent / absolute.name
```

Catch `OSError` and `RuntimeError` from parent resolution and convert them to the existing validation/recovery failure path. Compare the resolved parent/candidate against the resolved private root without resolving `candidate` itself. Leave final-entry classification to the existing `lstat`/`O_NOFOLLOW` installer checks.

- [ ] **Step 5: Make directory durability part of atomic publication**

Add one private helper in `validate_synastry.py` that opens a directory read-only, `fsync`s it, and closes it. Call it after every successful new link or exchange has been validated and before `_write_atomic_bytes` returns. Do not suppress directory-sync failures. Session finalization must therefore retain `.committing-<token>` when durability is unproven and succeed idempotently on recovery once the sync works.

- [ ] **Step 6: Bound fallback expiry and isolate recovery failures**

Compute malformed-state fallback using the current clock:

```python
observed_mtime = min(int(os.lstat(candidate).st_mtime), int(time.time()))
return observed_mtime + MAX_TTL_SECONDS + _CLOCK_GRACE_SECONDS
```

Ensure the known path-resolution failure types are converted to `_recover_committing(...) == False`. Keep `_sweep_expired` processing other owned states when one committing recovery returns false. Do not broadly swallow programming errors.

- [ ] **Step 7: Verify GREEN and regression coverage**

Run sequentially with the pinned Python 3.11–3.13-compatible requirements:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests/synastry_reading_skill -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python scripts/validate-repository.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-evals.py --check
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-descriptions.py --report
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync-shared.py --check
uvx ruff check .
uvx ruff format --check .
shellcheck scripts/*.sh
git diff --check
```

Expected: every command exits zero; all new tests exercise observable behavior and the full repository suite remains green.

- [ ] **Step 8: Commit the hardening task**

```bash
git add \
  plugins/astrology/skills/synastry-reading/scripts/reading_session.py \
  plugins/astrology/skills/synastry-reading/scripts/validate_synastry.py \
  tests/synastry_reading_skill/test_reading_session_state_machine.py \
  tests/synastry_reading_skill/test_validate_synastry.py
git commit -m "fix: harden synastry session durability"
```
