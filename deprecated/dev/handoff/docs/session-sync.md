# Session synchronization and orchestration

## Accepted behavior

Synchronize local Claude Code and Codex conversations in both directions and
publish Claude conversation indexes to every existing local account. Codex uses
one local task database without an account column. Remote cloud conversations
are outside this local-store contract.

Preserve original transcripts and any conversation continued independently in
either application. A continuation is a branch: it must reach the other client,
but must never overwrite a branch that the other client has started writing.
Repeated reconciliation without new conversation content must create nothing.

## Implementation

1. Discover top-level conversations from the Claude transcript store and Codex's
   read-only task database. Exclude subagents. Compare conversation content, not
   incidental file timestamps, to distinguish continuations from metadata writes.
2. Import Claude conversations through Codex's native app-server session import
   API. Verify the returned task is readable. The native importer updates an
   untouched import in place, but preserves an import that Codex has resumed.
   When it preserves such a task, import a separate managed snapshot for the new
   Claude branch. Never insert or update task database rows ourselves.
3. Render Codex history into a separately owned Claude transcript and publish
   its index under every existing account. If that transcript was continued in
   Claude, preserve it and publish subsequent Codex history to a new branch.
4. Track generated transcript content and native imports to prevent mirrors
   from bouncing back as new conversations. Adopt existing native imports and
   retain the old handoff state as recovery evidence.
5. Serialize reconciliation with a process lock, persist state atomically, and
   report errors rather than treating a swallowed hook error as success. Install
   a stable runner and a local watcher so synchronization does not depend on a
   particular desktop session reloading its hooks. Keep account visibility
   reconciliation idempotent and preserve each account's archive choices.
6. Verify orchestration separately: Claude's Fable model dispatches implementation
   and verification to the configured Opus and Sonnet agents; Codex dispatches
   to its configured child model. Preserve client permission and hook trust
   boundaries. Distinguish synthetic hook tests from actual model execution.

## Validation and delivery

Add failing boundary tests before implementing the storage, native transport,
and reconciliation changes. Exercise initial copy, incremental copy, continuation
on either side, concurrent branches, repeated execution, partial records,
invalid paths, unavailable clients, and all-account index publication. Run the
repository's complete documented gate before pushing a feature branch.

For local acceptance, import a synthetic conversation through the native API,
read it through the app, verify a continuation reaches the other store, and
check all existing Claude account indexes. Then run the historical backfill,
verify persisted outcomes, install the watcher, and observe its autonomous
incremental execution. Keep release, local installation, and UI/account-switch
evidence distinct.

## Current release gate

The feature branch has passed the full repository gate: 1,117 Python tests
with one expected platform skip, 83% runtime coverage against an 82% floor,
and the formatting, shell, registry, installation and evaluation structure checks.
Independent review found no remaining spec or standards findings. Regression
coverage includes archived native imports, adoption of existing imports, and
continued histories after rollout relocation.

Fresh desktop verification exercised Fable dispatch to the Opus implementer and
Sonnet verifier, including exact output-byte checks. Codex parent and child
execution was verified independently. Local readback verified 1,134 native Codex
tasks, 326 Claude copies, and all 1,459 expected transcript indexes in each of
four accounts. A fresh background-only fixture completed both directions and
returned a continued Claude copy as a preserved native branch; three later
watcher cycles completed without errors or fixture duplication.

The published skill received bounded wording corrections through two evaluation
iterations. The iteration records retain model identity, immutable run provenance,
scored tuning and holdout outcomes, and comparison gates. Earlier records affected
by suite fingerprint bookkeeping remain historical evidence, not passing gates.
`drafts/handoff-continuous-sync.md` remains an unaccepted broader rewrite; it is
not the installed or evaluated candidate. This release packages the implementation
and these tested instructions.
Installed client caches remain derived copies of the same repository release.

Removed working directories are imported through managed snapshots whose task
working directory is the closest existing parent. Original transcripts and
their recorded working directory remain unchanged. Stage these histories before
native discovery so a missing directory cannot trigger a full rescan per file.
Fork identity comes from the UUID filename, since inherited transcript prefixes
can still name the parent session. Copies and recovery journals are private files.

Claude desktop identity is distinct from transcript identity. Match indexes by
`cliSessionId`, preserve an existing desktop `sessionId`, and reuse that entry
when publishing to each account. Do not assume the index filename contains the
transcript UUID. Recoverably archived duplicate aliases remain excluded from
title selection and future publication.
