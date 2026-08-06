# Contributing

## Setup

```bash
git clone https://github.com/Misoto22/skills.git
cd skills
python3 scripts/validate-repository.py
```

Python 3.11+ and Bash are the whole toolchain. `ruff` is the one optional extra; CI runs it either way.

```bash
uvx ruff check . && uvx ruff format .
```

## Adding a skill

```bash
python3 scripts/new-skill.py <plugin> <skill>
```

That writes the skill and registers it in all five places the validator checks, creating the plugin if it does not exist. Three things are then yours:

1. **The description.** It is the only field that decides whether the skill ever fires. Say in concrete terms when to use it, name the phrasings and artefacts that should trigger it, and end with what it is not for. Keep it one line — the frontmatter parser reads plain key/value pairs and does not fold. `scripts/check-descriptions.py` holds you to all of that: it fails on a scaffold placeholder, on a description under 120 or over 1024 characters, on one that never says what the skill is not for, and on two skills sharing more than seven consecutive words. The last rule is the one no single skill's tests can catch — two descriptions competing for the same prompt means one of them misfires.
2. **The body.** Concrete and executable: specific rules, banned constructions, worked before-and-after pairs. An abstract exhortation is noise wherever it sits, so drop it rather than promote it.
3. **The placeholders** left in `README.md` and the plugin's `skills/README.md`.

Which plugin a skill belongs to is a judgement about subject, not convenience. `writing` is prose aimed at a person; `docs` is prose aimed at whoever opens the repository next. Two skills that would not sensibly share one `shared/` directory belong in different plugins — users install plugins independently, so a plugin spanning unrelated subjects makes them take skills they did not want.

## The constraint that governs skill content

Every installer copies a plugin — or, on most agents, a single skill directory — and nothing above it. A path that climbs out with `../` resolves in this repository and dangles everywhere else, and only Claude Code expands `${CLAUDE_*}`. Both are rejected in published skill content, and `scripts/verify-install.py` checks it against real installed trees rather than against this repository.

Shared material therefore lives in `plugins/<plugin>/shared/`, and `scripts/sync-shared.py` vendors a copy into each skill. Edit the plugin-level copy only; the validator, the packager, and CI all fail on drift.

## Before opening a pull request

```bash
uvx ruff check . && uvx ruff format --check .
shellcheck scripts/*.sh
python3 scripts/bump-version.py --audit
python3 scripts/ci-pins.py check
python3 scripts/check-descriptions.py
python3 scripts/validate-repository.py
```

The last one runs the metadata checks and then the full test suite. CI runs the same six plus an install of every plugin through all four routes.

The CLI versions CI installs live in `.ci-pins.json` and nowhere else — workflows ask for a spec with `python3 scripts/ci-pins.py spec <id>`, and `check` rejects any version written down that the file does not account for. Move one with `python3 scripts/ci-pins.py bump <id> <version>`. A literal pin is not just duplication: `CI_CHANNEL=latest` cannot override it, so it would be the one route the weekly canary silently keeps testing at the old version.

Tests come before implementation, and a change to what a script asserts needs a test that fails without it.

## Commits and pull requests

- English, imperative mood, under 72 characters on the subject line.
- One logical change per commit.
- Say why in the body, not what — the diff already carries what.
- Feature branches only. `main` is never force-pushed.

## Releasing

```bash
python3 scripts/bump-version.py <version>
```

Then update `CHANGELOG.md`, close `## Unreleased` with the version and date, merge, and tag:

```bash
git tag -a v<version> -m "skills v<version>" && git push origin v<version>
```

The tag builds a `.skill` for every published skill and attaches them to a GitHub Release, which is how claude.ai and Cowork are served on a personal plan.

New skills are a minor bump. A change to an install string or a command prefix is breaking, and in 0.x that also belongs in the minor position.
