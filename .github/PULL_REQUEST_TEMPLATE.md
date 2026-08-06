## What this changes

<!-- One or two sentences. The diff carries the what; say why. -->

## Checks

<!-- CI runs these too. Ticking them before pushing is faster than a red run. -->

- [ ] `uvx ruff check . && uvx ruff format --check .`
- [ ] `shellcheck scripts/*.sh`
- [ ] `python3 scripts/validate-repository.py` — metadata, registries, and the full suite
- [ ] `python3 scripts/bump-version.py --audit`
- [ ] `python3 scripts/ci-pins.py check`
- [ ] `python3 scripts/check-descriptions.py`
- [ ] `python3 scripts/run-evals.py --check`

## If this adds or changes a skill

- [ ] The `description` says when to use it, in terms that would actually trigger, and ends with what it is not for
- [ ] The body is concrete — specific rules, banned constructions, worked pairs — with no abstract exhortations
- [ ] No `../` and no `${CLAUDE_*}` in published skill content
- [ ] Anything cross-cutting went into `plugins/<plugin>/shared/`, not into two SKILL.md files
- [ ] `evals/<skill>/evals.json` covers what it must fire on and what it must stay out of
- [ ] `python3 scripts/verify-install.py` passes against a real install, not just the repository

## If this changes the published surface

- [ ] `PUBLISHED`, `marketplace.json`, both READMEs, `.version-bump.json`, and `skills.sh.json` all agree
- [ ] Scaffolded with `new-skill.py` or retired with `remove-skill.py`, rather than edited by hand

<!-- The install workflow is deliberately not on that list: it derives the plugin
     list and the expected skill names from the tree, so no name is written there. -->

## If this moves a CLI pin

- [ ] Moved with `python3 scripts/ci-pins.py bump <id> <version>`, never by editing a workflow
