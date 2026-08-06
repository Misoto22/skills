# Changelog

All notable changes to this repository are documented here.

## Unreleased

- **Breaking:** restructured the repository into a multi-plugin marketplace. The marketplace is now `misoto22` and the email skill is published by a `writing` plugin, so the install string is `writing@misoto22` and the command is `/writing:email`. The previous `skills@skills` install no longer resolves; reinstall from the new marketplace.
- Moved published skills from `skills/<name>/` to `plugins/writing/skills/<name>/`, and the plugin manifest from the repository root to `plugins/writing/.claude-plugin/`.
- Added the `tempering` skill (`/writing:tempering`), which rewrites blunt or frustrated workplace messages into three registers — collegial, direct but measured, and on the record — while preserving the request, the date, and the consequence that the raw tone was carrying. Renamed from `emo-to-memo` during import.
- Added `plugins/writing/shared/tone.md` and `format.md`, holding the apology, inflation, filler, fact-preservation, channel, language, and structure rules that `email` and `tempering` were each stating separately. Both skills now read them on demand via `${CLAUDE_SKILL_DIR}/../../shared/` instead of restating them.
- `package-skill.py` now copies the plugin's `shared/` into every `.skill` archive and rebases the reference, so an uploaded skill is self-contained on claude.ai and Cowork.
- Added a release workflow: pushing a `v*` tag packages every published skill and attaches the `.skill` files to a GitHub Release.
- Added an optional policy `style` profile that renders the generated HTML with inline typography, spacing, table, and status-colour tokens. Absent or `null` style keeps the previous bare semantic output.
- Added pipe-table and `[!ok]`/`[!warn]`/`[!bad]` status-marker markup to `body.txt`, so styled tables stay generated from the plain-text source instead of hand-written HTML.
- Added `list_style: paragraph` for composers that mangle pasted list indentation.
- Added `--policy` to `render_email.py`; `validate_message.py` now regenerates HTML with the same profile so the byte comparison still proves the HTML came from `body.txt`.

## 0.1.0 — 2026-08-03

- Added the configurable `email` skill with draft and verified-send modes.
- Added strict policy and message-bundle validation, deterministic HTML rendering, artifact hashing, and Sent-message readback comparison.
- Added optional Humanizer integration with protected-fact enforcement.
- Added monorepo registries, Claude plugin manifests, local linking, deterministic packaging, validation, tests, and CI.
