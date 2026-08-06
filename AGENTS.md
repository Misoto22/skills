# Repository guidance

## Layout

- The repository is a marketplace. Plugins live under `plugins/<plugin>/`, each with its own `.claude-plugin/plugin.json`, and publish skills from `plugins/<plugin>/skills/<skill>/`.
- Marketplace name, plugin name, and skill directory name are three separate things. The plugin name becomes the command prefix, so `writing` + `email` gives `/writing:email`.
- Plugin names must be kebab-case: lowercase letters, digits, and hyphens only. Claude Code is lenient here; the claude.ai marketplace sync is not.
- A plugin is copied to a cache directory on install, so nothing outside the plugin directory exists at runtime. Never reference `../` out of a plugin. Shared material goes in `plugins/<plugin>/shared/`, duplicated per plugin where two plugins need the same file.
- Skills reach shared material as `${CLAUDE_SKILL_DIR}/../../shared/<file>`, written as a code span rather than a markdown link so the validator's escape check still holds. `package-skill.py` copies `shared/` into each `.skill` and rebases the reference.
- Only release-ready skills may live under a plugin's `skills/`; use a top-level `drafts/` for unfinished work and `deprecated/` for retired material.

## Content

- Keep all code identifiers, comments, documentation, and commit messages in English.
- Explore existing skills and tests before changing behavior.
- Every published skill requires `SKILL.md`, `agents/openai.yaml`, a registry entry in both READMEs, tests, and matching plugin metadata.
- Cross-cutting writing rules belong in `shared/`, not in two SKILL.md files. What goes there is concrete and executable — specific rules, banned constructions, worked before/after pairs. Abstract exhortations belong nowhere.
- Preserve organization neutrality: no personal identity, company domain, credentials, local absolute path, or provider-specific transport assumption in runtime content, including `shared/`.
- Default ambiguous or incomplete outbound email intent to draft. Never weaken send authorization, disclosure, artifact-integrity, or readback gates — those live in the email skill and must not be relocated to `shared/`.
- Use dependency-free Python for portable runtime validation unless a reviewed design explicitly justifies a dependency.
- Add tests before implementation and run `python3 scripts/validate-repository.py` before release.
- Do not force-push `main` or `master`.
