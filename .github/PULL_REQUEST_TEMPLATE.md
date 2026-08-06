## What this changes

<!-- One or two sentences. The diff carries the what; say why. -->

## Checks

<!-- CI runs these too. Ticking them before pushing is faster than a red run. -->

- [ ] `uvx ruff check . && uvx ruff format --check .`
- [ ] `shellcheck scripts/*.sh`
- [ ] `python3 scripts/validate-repository.py` — metadata, registries, and the full suite
- [ ] `python3 scripts/bump-version.py --audit`

## If this adds or changes a skill

- [ ] The `description` says when to use it, in terms that would actually trigger, and ends with what it is not for
- [ ] The body is concrete — specific rules, banned constructions, worked pairs — with no abstract exhortations
- [ ] No `../` and no `${CLAUDE_*}` in published skill content
- [ ] Anything cross-cutting went into `plugins/<plugin>/shared/`, not into two SKILL.md files
- [ ] `python3 scripts/verify-install.py` passes against a real install, not just the repository

## If this changes the published surface

- [ ] `PUBLISHED`, `marketplace.json`, both READMEs, and the install workflow's `--expect` list all agree
