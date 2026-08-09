# Synastry Session Durability Design

**Status:** Approved on 2026-08-10 as the independent hardening cycle required after the Synastry v2 Task 7 review breaker.

## Goal

Close the four remaining output-path, durability, expiry, and recovery-scan defects without changing the public JSON-only calculator or reader workflows.

## Context

The reader persists private session material through explicit staging, public, finalizing, cancelling, and committing states. Exact-byte recovery is already content-addressed and concurrent claims use same-parent renames. The remaining defects sit at two internal seams: final destination classification and the point at which a published directory entry becomes durable.

## Considered approaches

1. **Targeted seam hardening — selected.** Preserve the state machine and CLI, add no-follow destination normalization, make parent-directory durability part of atomic publication, bound malformed-state fallback against the current clock, and isolate recovery errors per state. This keeps risk and review scope small.
2. **Replace paths with a directory-descriptor-only implementation.** Stronger against every ancestor swap, but requires a broad rewrite of validation, overwrite recovery, and platform adapters. It is disproportionate to the reproduced findings.
3. **Move sessions into a database or daemon.** Provides centralized transactions but adds a runtime dependency and deployment model that conflict with the portable skill contract.

## Design

### Destination classification

The final path component must never be dereferenced before validation. Convert a user path to an absolute lexical path, resolve only its parent when checking whether it lies inside the private session root, then pass the unchanged final component to the existing `lstat`/`O_NOFOLLOW` installation checks. A symlink, FIFO, socket, device, directory, or source alias at the destination is a refusal and leaves `.committing-<token>` intact.

Persisted destination validation follows the same helper. Path-resolution failures, including a symlink loop in an ancestor, become a per-commit recovery failure rather than escaping the sweep.

### Durable publication

Atomic installation owns durability. After a hard-link publication or exchange has produced and verified the exact destination entry, `fsync` the destination's parent directory before returning success. The session layer deletes `.committing-<token>` only after the installer returns and stable exact-byte readback succeeds. If the directory sync fails, the commit remains recoverable and the operation reports failure.

This behavior belongs inside the existing atomic-write module so direct validated writes and recovered session writes share one durability contract.

### Bounded malformed-state expiry

Valid persisted leases remain authoritative. For missing or malformed lease data, the fallback deadline is derived from `min(state_mtime, current_time)` plus the one-hour maximum and clock grace. A future filesystem timestamp therefore cannot extend retention beyond the advertised bound from the current observation.

### Recovery isolation

Each committing state is recovered independently. Unsafe paths, malformed manifests, symlink loops, and installation failures retain that state and return a failed recovery result; they do not abort `_sweep_expired` or prevent creation of unrelated new sessions. Unexpected programming errors remain visible rather than being swallowed broadly.

## Error and safety invariants

- No final destination symlink or other special entry is followed or overwritten.
- No committed recovery state is deleted until destination directory durability and exact stable output readback are both proven.
- Malformed private state is retained for no longer than `MAX_TTL_SECONDS + _CLOCK_GRACE_SECONDS` from the current observation, even with a future `mtime`.
- One bad committing state cannot crash startup sweeping or block unrelated sessions.
- Existing JSON schemas, commands, output status shapes, privacy rules, and organization-neutral skill text do not change.

## Verification

Tests must first reproduce all four defects against commit `19b09ac`. Focused tests cover final-component symlinks to absent and exact targets, parent-directory `fsync` ordering/failure, future-mtime expiry, and a persisted destination with a symlink loop. Regression verification includes all reader tests, skill contracts, the full repository suite, repository validation, Ruff, format, ShellCheck, shared-copy drift, and diff checks in the supported pinned Python environment.
