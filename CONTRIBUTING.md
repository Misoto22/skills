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
4. **The evaluation cases**, at `evals/<skill>/evals.json` — at least three prompts it must fire on and two it must stay out of, plus one held-out case per section. `scripts/run-evals.py --check` fails until they exist, and `--report` prints them for a manual run. The non-triggers are the ones worth thinking about: a skill that fires on everything looks perfect in its own trigger cases, and the damage lands on whichever skill it took the prompt from. See [evals/README.md](evals/README.md).

Where a rule belongs is decided before which skill it goes in. Deterministic work — a calculation, a validation, a layout — is a script the skill runs, with tests, not a paragraph the model re-derives. A rule the model must never break is a hook in `plugins/<plugin>/hooks/`, which refuses the command before it runs; the prose then says what to do, not what to avoid. A long private session whose transcript the caller never needs is a fork (`context: fork` in the skill's frontmatter) rather than an inline run. What is left — judgement, sequence, and the reasons behind them — is the skill.

Which plugin a skill belongs to is a judgement about subject, not convenience. `writing` is prose aimed at a person; `docs` is prose aimed at whoever opens the repository next. Two skills that would not sensibly share one `shared/` directory belong in different plugins — users install plugins independently, so a plugin spanning unrelated subjects makes them take skills they did not want.

## Retiring a skill

```bash
python3 scripts/remove-skill.py <plugin> <skill>
```

The inverse of `new-skill.py`, unwinding the same registrations plus the evaluation suite, and clearing any `routes_to` in another skill's cases that named it. The material moves to `deprecated/<plugin>/<skill>/` with its cases beside it; `--delete` removes it instead. Emptying a plugin retires the plugin — manifest, marketplace entry, and directory group.

Nothing published looks into `deprecated/` or `drafts/`. They are outside `plugins/`, so no installer, packager, or registry sees them, and the version audit and pin scan skip them; a test asserts all of that against a real retirement.

## Changing a skill's wording

An edit to a published `SKILL.md` goes through [evals/ITERATION.md](evals/ITERATION.md): measure the tuning split, write down both what failed *and* what passed that the edit could break, make **at most three edits**, then keep the edit only if the tuning score rose and the held-out score did not fall.

Two of those are not habits, they are load-bearing. The held-out cases exist because a skill re-measured on the cases that produced its wording scores that wording back — `email` iteration-1 reached 100% by narrowing wording in response to `ambiguous-reply` and then re-scoring `ambiguous-reply`. And the three-edit budget exists because an iteration grades ten to twenty expectations: past three simultaneous edits a moved score cannot be attributed, and the cheap response — revert all three — discards the one that worked. Anything tried and dropped goes in that iteration's `rejected.md`, or the next person re-proposes it.

## The constraint that governs skill content

Every installer copies a plugin — or, on most agents, a single skill directory — and nothing above it. A path that climbs out with `../` resolves in this repository and dangles everywhere else, and only Claude Code expands `${CLAUDE_*}`. Both are rejected in published skill content, and `scripts/verify-install.py` checks it against real installed trees rather than against this repository.

Shared material therefore lives in `plugins/<plugin>/shared/`, and `scripts/sync-shared.py` vendors a copy into each skill. Edit the plugin-level copy only; the validator, the packager, and CI all fail on drift.

The one place `${CLAUDE_PLUGIN_ROOT}` is allowed is a plugin's `hooks/hooks.json`: a hook only ever runs where the plugin was installed, so the plugin root is guaranteed there and nowhere a skill is copied alone.

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

Nobody cuts a release by hand. `release-please` does, from the pull-request titles that landed on `main`, which is
the other reason the title has to be a Conventional Commit and why `pr-title / pr-title` is a required check.

Merging a `feat:` or `fix:` pull request makes the bot open or update one called `chore(main): release X.Y.Z`. That
pull request rewrites every versioned file listed under `extra-files` in `release-please-config.json` — both plugin
manifests per plugin, every `SKILL.md` front matter, `registry.json`, the validator's `VERSION`, and the two test
constants — and writes the `CHANGELOG.md` entry. Review it like any other pull request; the whole gate runs on it.
Merging it tags `vX.Y.Z`, publishes the GitHub Release, and `release.yml` then builds a `.skill` for every published
skill and attaches them to it, which is how claude.ai and Cowork are served on a personal plan.

What decides the number is the commit type: `fix:` is a patch, `feat:` a minor, and a `!` or a `BREAKING CHANGE:`
trailer a major. New skills are a minor. A change to an install string or a command prefix is breaking, and in 0.x
that belongs in the minor position — so write it as `feat!:` only once this repository is past 1.0.

`scripts/bump-version.py <version>` still exists for a correction the bot cannot make, and `--audit` is now the check
that `release-please-config.json` and `.version-bump.json` still describe the same set of files:

```bash
python3 scripts/bump-version.py --audit
```

A file that carries the version and is declared in only one of them fails that check. A new `SKILL.md` is registered
in both by `scripts/new-skill.py`, and every file release-please rewrites in place carries a
`# x-release-please-version` comment on the line holding the version — delete it and the release walks past the file.
