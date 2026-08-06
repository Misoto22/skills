# skills

Portable, configurable agent skills for reliable everyday work.

The repository is a marketplace named `misoto22`. Each plugin under `plugins/` publishes its own skills, and the plugin name becomes the command prefix — the `writing` plugin gives you `/writing:email`, the `docs` plugin gives you `/docs:readme`.

```
.claude-plugin/marketplace.json   # marketplace: misoto22
plugins/
  writing/                        # plugin: writing  -> /writing:*
    .claude-plugin/plugin.json
    shared/                       # reference material its skills read on demand
    skills/
      email/
      tempering/
  docs/                           # plugin: docs     -> /docs:*
    .claude-plugin/plugin.json
    skills/
      readme/
```

A plugin is a subject, not a bucket. `writing` covers prose aimed at a person; `docs` covers prose aimed at whoever opens the repository next. Skills that would not share a `shared/` directory belong in different plugins.

Shared material lives inside the plugin that uses it. Installers copy a plugin — or, for most agents, a single skill directory — and nothing above it, so a reference that climbs out with `../` resolves in the repository and dangles after install. `plugins/writing/shared/` is the only copy anyone edits; `scripts/sync-shared.py` vendors it into each `skills/<skill>/shared/`, and CI fails on drift.

## Published skills

| Skill | Command | Purpose | Version |
| --- | --- | --- | ---: |
| [email](plugins/writing/skills/email/SKILL.md) | `/writing:email` | Draft policy-aware email or send exact validated artifacts with Sent-message readback verification. | 0.2.0 |
| [tempering](plugins/writing/skills/tempering/SKILL.md) | `/writing:tempering` | Rewrite a blunt or frustrated workplace message into three registers without losing the request. | 0.2.0 |
| [readme](plugins/docs/skills/readme/SKILL.md) | `/docs:readme` | Write, restructure, or audit a repository README from what its own files say. | 0.2.0 |

## Install

Pick the row that matches your agent. All four routes are exercised by CI on every push, against the tree the installer actually produces.

| Agent | Route |
| --- | --- |
| Claude Code | plugin marketplace |
| Codex | plugin marketplace |
| Cursor, Windsurf, opencode, Roo, Kilo Code, Qwen, iFlow, Trae, Junie, Continue, Goose, Crush, and ~40 more | `npx skills` |
| claude.ai, Cowork | `.skill` upload |

### Claude Code

```bash
claude plugin marketplace add Misoto22/skills
```

```bash
claude plugin install writing@misoto22
```

```bash
claude plugin install docs@misoto22
```

Gives you `/writing:email`, `/writing:tempering`, and `/docs:readme`. Install only the plugins you want — each is independent.

### Codex

Codex reads the same marketplace manifest.

```bash
codex plugin marketplace add https://github.com/Misoto22/skills
```

```bash
codex plugin add writing@misoto22 && codex plugin add docs@misoto22
```

### Everything else — `npx skills`

One command installs into every agent directory found on the machine. Drop `--agent '*'` to be prompted for a subset, or name one (`--agent cursor`).

```bash
npx --yes skills@1.5.20 add Misoto22/skills --agent '*' --skill '*'
```

This is a copied installation: it does not track the repository, so rerun the command to update.

### claude.ai and Cowork

Marketplace sync is an organization feature, so on a personal plan these two need a file. Download the `.skill` archives from the [latest release](https://github.com/Misoto22/skills/releases/latest) and upload them in the skills UI.

Every route above installs a self-contained skill: the shared reference files ship inside each skill directory, so nothing dangles once the skill leaves this repository.

### Local clone

Substitute the clone's path for `Misoto22/skills` in any command above — `claude plugin marketplace add .`, `codex plugin marketplace add "$PWD"`, `npx skills add .`.

Maintainers who want editable installs rather than copies may run `bash scripts/link-skills.sh`. It links only published skill directories, never overwrites real files or directories, and stops on conflicts.

## Use email

Copy [`plugins/writing/skills/email/policy.example.json`](plugins/writing/skills/email/policy.example.json) to `.agents/email-policy.json` in a project and replace the reserved example identity. Draft is always the default; automated send remains disabled until a narrow local scope is explicitly configured. See [docs/email.md](docs/email.md).

## Development

```bash
python3 -m unittest discover -s tests -v
```

```bash
python3 scripts/validate-repository.py
```

```bash
bash scripts/list-skills.sh
```

```bash
python3 scripts/sync-shared.py
```

```bash
python3 scripts/package-skill.py plugins/writing/skills/email dist
```

`scripts/verify-install.py <dir>` asserts an installed tree is complete and self-contained; point it at any real install to reproduce what CI checks. Tagging `v*` builds a `.skill` for every published skill and attaches them to a GitHub Release.

The repository contains no transport credentials and does not implement SMTP. License: [MIT](LICENSE).
