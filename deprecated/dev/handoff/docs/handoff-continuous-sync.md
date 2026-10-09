# Continuous handoff candidate

This runtime candidate is not a published skill replacement. Its wording gate
could not run without the scoped evaluation credential. Keep the existing
published instructions until tuning improves and the held-out score does not
fall. The runtime contract and acceptance procedure are in docs/session-sync.md.

From the handoff skill directory, run:

```bash
python3 scripts/handoff.py sync           # report planned changes
python3 scripts/handoff.py sync --apply   # reconcile both local stores
python3 scripts/handoff.py install        # install stable runner, hooks and watcher
python3 scripts/handoff.py status
python3 scripts/handoff.py uninstall      # keep histories and ownership records
```

Applying uses Codex's native import API and verifies each task through native
readback. It reads Codex's database without writing rows, creates separate
Claude transcripts in their project directories, and publishes indexes to all
existing local Claude accounts. It excludes subagents and cloud-only tasks.

Installation backs up hook settings and registers only this runtime's hooks.
On macOS it also installs its own launch agent. Explain these edits before
installation and proceed when the user's request already authorizes them.
Other platforms report the watcher as not installed. Hooks only request a
background scan; their success does not imply that synchronization succeeded.

Preserve originals and independently continued branches. An untouched import
can update in place; a resumed import is preserved, and the changed source is
imported as a separate snapshot. A Claude copy continued by the user is also
preserved; subsequent Codex history gets a new copy. Retain ownership for every
copy to prevent automatic histories from circulating as new sources.

Report applied, unchanged, pending and failed results separately. Check the
watcher report for failures. Corrupt ownership state stops synchronization;
never silently reset it. A transcript file alone does not prove native Codex
registration. Claude index verification does not prove sidebar visibility.
Observe an independent new source after installation before claiming that the
watcher works.

Converted context is readable history, not a byte-exact provider replay.
Encrypted reasoning, signed thinking, attachments and provider-specific state
are not guaranteed to survive conversion. Imported context can be continued in
a new task, and that continuation is a distinct branch.
