# Changelog

All notable changes to this repository are documented here.

## Unreleased

- Added `/dev:sync`, which fetches, prunes, and fast-forwards the base branch, then reports what diverged. It only fast-forwards: a diverged branch is reported, never rebased, because choosing between rebase, merge, and reset is the user's call and guessing it destroys work. On a feature branch it advances the base with `git fetch origin <base>:<base>`, which never touches the working tree.
- Added `/dev:cleanup`, which removes merged branches, their worktrees, and ignored residue a move stranded. Every deletion is verified against the forge rather than against git, and a branch marked `[gone]` with no merged pull request is kept and reported — that is abandoned work or someone else's mistake, and it is unrecoverable once the local copy is gone.
- Added `plugins/dev/shared/git.md`, now that three skills need the same rules: base resolution, the force-push rule, why `git branch --merged` does not list a branch that landed through a rebase or squash merge, and that `git mv` strands ignored files where `git status` will never mention them. `ship` no longer restates base resolution.

## 0.6.0 — 2026-08-06

- Added the `dev` plugin and its `ship` skill (`/dev:ship`), which lands the current changes as a merged pull request: preflight, branch, test, commit, PR, CI, merge, worktree cleanup. A clean tree on the base branch exits without doing anything, and any step that fails twice stops and asks.
- `ship` gained three things over the version it was imported from: a secrets gate before staging, since shipping is the last step before a change becomes public and a pushed credential is compromised even after a force-push; merge-strategy detection from what the repository allows and how many commits the branch carries, rather than always squashing; and `--dry-run`, which prints the execution plan and stops.
- `new-skill.py` now also registers the new skill in `.version-bump.json` — a new `SKILL.md` carries a version, and the scaffolder was leaving it undeclared for the audit to catch later.
- The repository contract tests assert that the marketplace, the plugin manifests, the READMEs, and the skills on disk agree, instead of restating a frozen list of plugins that every scaffold had to edit.

## 0.5.0 — 2026-08-06

- Gave the README a committed SVG hero served per theme through `<picture>`, replacing a `src="[hero image URL]"` placeholder that rendered as a broken icon. Install routes fold into `<details>`, the plugin structure is a `mermaid` graph with the directory tree behind it, and three alerts carry the constraints a reader would otherwise miss.
- The `readme` skill now looks at the rendered page. Audit mode opens with whether the first screen renders, and a new section covers what to check there — including that rendered length is not source length, and that a leftover `<pre lang="mermaid">` is GitHub's hidden fallback rather than a failed diagram.
- `references/skeleton.md` ships the native components it argues for: `<details>` for alternate install routes, one alert, and a diagram slot, each with a comment saying when to delete it. The hero placeholder is gone entirely — the block is commented out with working two-theme markup inside.
- A heading may now take the word a project's own readers scan for, as long as it keeps its slot and its job. The order still does not change.
- The documented `npx skills` command no longer carries `--yes --agent '*' --skill '*'`. Those flags are for CI, and pasting them into a README hands every reader a silent install instead of the CLI's own interactive one; the scripted form is written out beside it. The CI pin moves to `skills@1.5.22`.

## 0.4.0 — 2026-08-06

- Added linting: `ruff.toml` selects the rules that catch real defects on a standard-library-only codebase, and CI runs `ruff check`, `ruff format --check`, and `shellcheck`. The first run found 47 findings, including five `subprocess.run` calls whose exit status was inspected but never declared with `check=`.
- Added `scripts/bump-version.py` and `.version-bump.json`. The version lives in eight files; `--audit` greps for occurrences the declared list does not cover and fails, so a tag cannot ship artefacts that disagree with it. CI runs the audit on every push.
- Added `scripts/new-skill.py`, which scaffolds a skill and registers it in all five places the validator checks, creating the plugin when it does not exist. A test scaffolds, validates, and rolls back, so the tool cannot drift from the checks it satisfies.
- Added `CONTRIBUTING.md`, a pull request template, two issue templates, and dependabot for the pinned GitHub Actions.

## 0.3.0 — 2026-08-06

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
