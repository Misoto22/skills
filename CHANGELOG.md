# Changelog

All notable changes to this repository are documented here.

## Unreleased

- Added the `docs` plugin and its `readme` skill (`/docs:readme`), which writes, restructures, and audits a repository README from what the repository's own files say, against the house style. Reads the manifest, task runner, and tree before writing, and leaves a bracketed placeholder wherever a fact is unavailable rather than inventing a version number.
- Generalised the repository from one plugin to many: the validator asserts a `PUBLISHED` map of plugin to skills, the marketplace registers each plugin separately, and `verify-install.py` derives a skill's required `shared/` files from its own text instead of a fixed list, so a single-skill plugin needs no `shared/` directory.
- Both link checkers now skip fenced code blocks, so a skeleton containing sample markup is no longer read as a broken reference.

## 0.2.0 — 2026-08-06

- **Breaking:** restructured the repository into a multi-plugin marketplace. The marketplace is now `misoto22` and the email skill is published by a `writing` plugin, so the install string is `writing@misoto22` and the command is `/writing:email`. The previous `skills@skills` install no longer resolves; reinstall from the new marketplace.
- Moved published skills from `skills/<name>/` to `plugins/writing/skills/<name>/`, and the plugin manifest from the repository root to `plugins/writing/.claude-plugin/`.
- Added the `tempering` skill (`/writing:tempering`), which rewrites blunt or frustrated workplace messages into three registers — collegial, direct but measured, and on the record — while preserving the request, the date, and the consequence that the raw tone was carrying. Renamed from `emo-to-memo` during import.
- Added `plugins/writing/shared/tone.md` and `format.md`, holding the apology, inflation, filler, fact-preservation, channel, language, and structure rules that `email` and `tempering` were each stating separately. Both skills read them instead of restating them. Installers copy a skill directory and nothing above it, so `scripts/sync-shared.py` vendors the plugin-level directory into each `skills/<skill>/shared/` and references stay skill-root-relative; the validator rejects `${CLAUDE_*}` and `../` in published skill content, which is what keeps a skill self-contained after install.
- Added Codex support: `codex plugin marketplace add` reads the same manifest, so `codex plugin add writing@misoto22` installs both skills.
- Added a release workflow: pushing a `v*` tag packages every published skill and attaches the `.skill` files to a GitHub Release.
- Added `scripts/verify-install.py`, which asserts an installed skill tree is complete and self-contained, and an Install workflow that runs it against all four install routes — Claude Code plugin, Codex plugin, `npx skills add` across every supported agent directory, and an unpacked `.skill`.
- Added an optional policy `style` profile that renders the generated HTML with inline typography, spacing, table, and status-colour tokens. Absent or `null` style keeps the previous bare semantic output.
- Added pipe-table and `[!ok]`/`[!warn]`/`[!bad]` status-marker markup to `body.txt`, so styled tables stay generated from the plain-text source instead of hand-written HTML.
- Added `list_style: paragraph` for composers that mangle pasted list indentation.
- Added `--policy` to `render_email.py`; `validate_message.py` now regenerates HTML with the same profile so the byte comparison still proves the HTML came from `body.txt`.

## 0.1.0 — 2026-08-03

- Added the configurable `email` skill with draft and verified-send modes.
- Added strict policy and message-bundle validation, deterministic HTML rendering, artifact hashing, and Sent-message readback comparison.
- Added optional Humanizer integration with protected-fact enforcement.
- Added monorepo registries, Claude plugin manifests, local linking, deterministic packaging, validation, tests, and CI.
