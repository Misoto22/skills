# Contributing

## Setup

```bash
git clone https://github.com/Misoto22/skills.git
cd skills
python3 scripts/validate-repository.py
```

Python 3.11+ and Bash are the whole toolchain. `ruff` and `coverage` are the only extras, both optional locally; CI runs them either way.

```bash
uvx ruff check . && uvx ruff format .
uvx coverage run -m unittest discover -s tests && uvx coverage report
```

Coverage is measured on `plugins/` — the Python that actually ships — and floored at whatever `fail_under` in
[`.coveragerc`](.coveragerc) declares. The figure is deliberately not repeated here: a number written down twice
drifts, and the copy nobody runs is the one that goes stale. The repository's own `scripts/` run through
subprocess in the contract tests, where the number would describe the harness rather than the code. Raise the
floor when the real figure rises; never lower it to make a run pass.

## Adding a skill

```bash
python3 scripts/new-skill.py <plugin> <skill>
```

That writes the skill and registers it in all five places the validator checks, creating the plugin if it does not exist. Three things are then yours:

1. **The description.** It is the only field that decides whether the skill ever fires. Say in concrete terms when to use it, name the phrasings and artefacts that should trigger it, and end with what it is not for. Keep it one line — the frontmatter parser reads plain key/value pairs and does not fold. `scripts/check-descriptions.py` holds you to all of that: it fails on a scaffold placeholder, on a description under 120 or over 1024 characters, on one that never says what the skill is not for, and on two skills sharing more than seven consecutive words. The last rule is the one no single skill's tests can catch — two descriptions competing for the same prompt means one of them misfires.
2. **The body.** Concrete and executable: specific rules, banned constructions, worked before-and-after pairs. An abstract exhortation is noise wherever it sits, so drop it rather than promote it.
3. **The placeholders** left in `README.md` and the plugin's `skills/README.md`.
4. **The evaluation cases**, at `evals/<skill>/evals.json` — at least three prompts it must fire on and two it must stay out of. `scripts/run-evals.py --check` fails until they exist, and `--report` prints them for a manual run. The non-triggers are the ones worth thinking about: a skill that fires on everything looks perfect in its own trigger cases, and the damage lands on whichever skill it took the prompt from. See [evals/README.md](evals/README.md).

Which plugin a skill belongs to is a judgement about subject, not convenience. `writing` is prose aimed at a person; `docs` is prose aimed at whoever opens the repository next. Two skills that would not sensibly share one `shared/` directory belong in different plugins — users install plugins independently, so a plugin spanning unrelated subjects makes them take skills they did not want.

## Retiring a skill

```bash
python3 scripts/remove-skill.py <plugin> <skill>
```

The inverse of `new-skill.py`, unwinding the same registrations plus the evaluation suite, and clearing any `routes_to` in another skill's cases that named it. The material moves to `deprecated/<plugin>/<skill>/` with its cases beside it; `--delete` removes it instead. Emptying a plugin retires the plugin — manifest, marketplace entry, and directory group.

Nothing published looks into `deprecated/` or `drafts/`. They are outside `plugins/`, so no installer, packager, or registry sees them, and the version audit and pin scan skip them; a test asserts all of that against a real retirement.

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
python3 scripts/run-evals.py --check
python3 scripts/build-registry.py --check
python3 scripts/validate-repository.py
```

The last one runs the metadata checks and then the full test suite. CI runs the same eight plus an install of every plugin through all four routes.

Model-scored evals are deliberately local at present: the public LiteLLM endpoint remains behind Cloudflare Bot Fight Mode, which GitHub-hosted runners cannot complete. Before pushing a routing or behavior change, export the scoped gateway key from the approved secret manager and run the affected suite:

```bash
LITELLM_EVALS_API_KEY=... bash scripts/run-evals-local.sh <skill>
```

Omit `<skill>` to score every routing and behavior case. The helper creates a temporary virtual environment, talks only to `https://llm-evals.misoto22.com/v1`, and removes the environment afterwards; it neither writes the key to disk nor contacts a model provider directly.

`build-registry.py --check` is the one that fails over a file you did not edit. `registry.json` is the catalogue every reader outside Claude Code fetches — the personal site renders it — and it is generated from `skills.sh.json`, `marketplace.json`, each `plugin.json` and each `SKILL.md`. `new-skill.py`, `remove-skill.py` and `bump-version.py` rebuild it for you; editing a description by hand does not, and a stale registry keeps serving the old wording. Run `python3 scripts/build-registry.py` and commit the result.

It also fails when a translation is missing. `i18n/<locale>.json` holds the reader-facing strings per language, and the build requires an entry for every published group and skill — and none for anything unpublished. The scaffold writes a PLACEHOLDER entry, which the build rejects until you write it, exactly as the validator rejects a scaffolded description. What is *not* translated is the SKILL.md body: it is the instruction an agent executes, so a second copy would be a second source nothing keeps in step. `overview` is the paragraph a reader in that language gets instead.

Every version CI depends on lives in `.ci-pins.json` and nowhere else — the CLIs it installs, the Python and Node
runtimes its jobs run on, and the model the weekly evaluation bills against. Workflows ask for a spec with
`python3 scripts/ci-pins.py spec <id>`, and `check` rejects any version written down that the file does not
account for. Move one with `python3 scripts/ci-pins.py bump <id> <version>`. A literal pin is not just
duplication: `CI_CHANNEL=latest` cannot override it, so it would be the one route the weekly canary silently
keeps testing at the old version. A pin whose version is not a semver — a runtime, a model name — declares its
own `version_pattern`.

Names are derived rather than written down for the same reason. `scripts/list-plugins.sh`,
`scripts/list-skills.sh`, `scripts/marketplace-name.sh` and `scripts/install-skill-requirements.sh` are what the
install workflow calls, so adding a plugin, a skill, or a skill's first dependency never edits CI.

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
