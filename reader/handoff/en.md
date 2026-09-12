`handoff` keeps readable conversation history available in Claude Code and Codex on the same machine. Its background watcher discovers both local stores, registers native Codex tasks, and creates Claude transcripts with indexes in every existing local Claude account.

## Set it up

From the installed skill directory:

```bash
python3 scripts/handoff.py sync           # preview the planned reconciliation
python3 scripts/handoff.py sync --apply   # apply one pass
python3 scripts/handoff.py install        # install the stable runner, hooks and watcher
python3 scripts/handoff.py status         # inspect installation and completion state
python3 scripts/handoff.py uninstall      # remove this service and hooks, keep histories
```

Installation backs up the hook settings, updates this skill's entries in `~/.claude/settings.json` and `~/.codex/hooks.json`, and preserves other hooks. On macOS it also installs its own launch agent. Reinstall after a plugin update to refresh the stable runner. Client hook trust remains under the client's control. Other platforms report the watcher as not installed; run `watch` or explicit sync passes where supported.

## How histories stay separate

A Codex rollout file alone is insufficient: the bridge uses native import and reads the resulting task back. Claude also needs a desktop index entry. The bridge matches the transcript's `cliSessionId` and preserves an existing desktop `sessionId`, including when those two IDs differ.

Untouched imports can receive updates. If either copy has been independently continued, the bridge preserves it and sends later history as a separate branch. Originals are retained. Histories from deleted working directories use a managed snapshot with an existing parent directory, leaving the recorded original unchanged.

## What to verify

A hook only requests a background scan. Its silent zero exit does not prove that any conversation synchronized. Read the latest watcher completion report and per-source failures, then open a fresh imported conversation in the destination application. All-account index checks and actual sidebar visibility are separate checks.

Large archives can take time to scan, especially after a watcher restart. Synchronization is eventual; a configured polling interval is not an end-to-end latency guarantee. Partial final lines wait until the next complete record.

## Limits

This preserves readable context, not a byte-exact provider replay. Encrypted reasoning, signed thinking, attachments and provider-specific state may not survive translation. Imported conversations can be continued as separate tasks. Subagents and cloud-only histories are excluded, and this is not a transfer between computers.
