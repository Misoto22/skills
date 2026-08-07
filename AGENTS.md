# Repository guidance

## Layout

- The repository is a marketplace. Plugins live under `plugins/<plugin>/`, each with its own `.claude-plugin/plugin.json`, and publish skills from `plugins/<plugin>/skills/<skill>/`.
- A plugin is a subject, not a bucket: `writing` is prose aimed at a person, `docs` is prose aimed at whoever opens the repository next. Two skills that would not sensibly share one `shared/` directory belong in different plugins. Users install plugins independently, so a plugin that spans unrelated subjects makes them take skills they did not want.
- `scripts/validate-repository.py` holds the published surface in `PUBLISHED`. Adding a plugin or skill means adding it there, to `marketplace.json`, and to both READMEs — the validator fails until all of them agree. The install workflow is not on that list: `scripts/list-plugins.sh` and `scripts/list-skills.sh` derive what it installs and what it expects, so a name is never written down there.
- Marketplace name, plugin name, and skill directory name are three separate things. The plugin name becomes the command prefix, so `writing` + `email` gives `/writing:email`.
- Plugin names must be kebab-case: lowercase letters, digits, and hyphens only. Claude Code is lenient here; the claude.ai marketplace sync is not.
- A plugin is copied to a cache directory on install, so nothing outside the plugin directory exists at runtime. Never reference `../` out of a plugin. Shared material goes in `plugins/<plugin>/shared/`, duplicated per plugin where two plugins need the same file.
- Every path a skill references must resolve from the skill root on every installer. `${CLAUDE_*}` variables and `../` are rejected in published skill content: only Claude Code expands the former, and only its plugin cache keeps a directory above the skill.
- `plugins/<plugin>/shared/` is the only copy anyone edits. `scripts/sync-shared.py` vendors it into `skills/<skill>/shared/`, and those copies are committed so a plain clone installs correctly. The validator, `package-skill.py`, and CI all fail on drift.
- Only release-ready skills may live under a plugin's `skills/`; use a top-level `drafts/` for unfinished work and `deprecated/` for retired material. Both sit outside `plugins/`, so no installer, packager, or registry sees them, and the version audit and pin scan skip them.
- Retire a skill with `python3 scripts/remove-skill.py <plugin> <skill>` rather than unwinding seven registrations by hand. It moves the skill and its evaluation cases under `deprecated/`, clears any `routes_to` that named it, and retires the plugin when that was its last skill.

## Content

- Keep all code identifiers, comments, documentation, and commit messages in English.
- Explore existing skills and tests before changing behavior.
- Every published skill requires `SKILL.md`, `agents/openai.yaml`, a registry entry in both READMEs, evaluation cases at `evals/<skill>/evals.json`, and matching plugin metadata. A skill shipping `scripts/` also requires unit tests; a prose skill's cases are its tests, which is why `scripts/run-evals.py --check` fails when a suite is missing.
- Every published plugin carries two manifests: `.claude-plugin/plugin.json`, which Claude Code reads and which requires a `skills` array, and `plugin.json` at the plugin root, which every Agent Plugins client reads and whose schema rejects that array. Where both exist the root one wins, so the validator asserts the fields they share are equal rather than merely present. `keywords` lives only in the root one — it is the field nothing in this repository reads and the one a plugin directory searches on.
- Client-specific material has two homes, and they are not interchangeable. `agents/openai.yaml` sits inside a skill and describes that skill to one client; the `extensions` object and its reverse-domain directories sit at the plugin root and describe the plugin. Nothing here uses `extensions` yet — a namespace is only allowed to be a domain someone owns, so a future one cannot collide with another client's.
- A description is held to `scripts/check-descriptions.py`, not to taste: one line, 120 to 1024 characters, no scaffold placeholder, an explicit statement of what the skill is not for, and no run of more than seven consecutive words shared with another description. `--report` prints the lengths and the overlap table.
- Cross-cutting writing rules belong in `shared/`, not in two SKILL.md files. What goes there is concrete and executable — specific rules, banned constructions, worked before/after pairs. Abstract exhortations belong nowhere.
- Preserve organization neutrality: no personal identity, company domain, credentials, local absolute path, or provider-specific transport assumption in runtime content, including `shared/`.
- Default ambiguous or incomplete outbound email intent to draft. Never weaken send authorization, disclosure, artifact-integrity, or readback gates — those live in the email skill and must not be relocated to `shared/`.
- Use dependency-free Python for portable runtime validation unless a reviewed design explicitly justifies a dependency.
- Add tests before implementation and run `python3 scripts/validate-repository.py` before release.
- Scaffold a skill with `python3 scripts/new-skill.py <plugin> <skill>` rather than registering it by hand, and move a release with `python3 scripts/bump-version.py <version>` rather than editing eight files.
- Never write a CLI version into a workflow. `.ci-pins.json` is the only place one lives; ask for a spec with `python3 scripts/ci-pins.py spec <id>`, move it with `bump`, and `check` fails on any literal it does not account for. A literal cannot be overridden by `CI_CHANNEL=latest`, which is what the canary run needs it for.
- Run `uvx ruff check .`, `uvx ruff format .`, and `shellcheck scripts/*.sh` before committing; CI enforces all three.
- Do not force-push `main` or `master`.
