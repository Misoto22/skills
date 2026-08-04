# Changelog

All notable changes to this repository are documented here.

## Unreleased

- Added an optional policy `style` profile that renders the generated HTML with inline typography, spacing, table, and status-colour tokens. Absent or `null` style keeps the previous bare semantic output.
- Added pipe-table and `[!ok]`/`[!warn]`/`[!bad]` status-marker markup to `body.txt`, so styled tables stay generated from the plain-text source instead of hand-written HTML.
- Added `list_style: paragraph` for composers that mangle pasted list indentation.
- Added `--policy` to `render_email.py`; `validate_message.py` now regenerates HTML with the same profile so the byte comparison still proves the HTML came from `body.txt`.

## 0.1.0 — 2026-08-03

- Added the configurable `email` skill with draft and verified-send modes.
- Added strict policy and message-bundle validation, deterministic HTML rendering, artifact hashing, and Sent-message readback comparison.
- Added optional Humanizer integration with protected-fact enforcement.
- Added monorepo registries, Claude plugin manifests, local linking, deterministic packaging, validation, tests, and CI.
