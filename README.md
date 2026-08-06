# skills

Portable, configurable agent skills for reliable everyday work.

The repository is a marketplace named `misoto22`. Each plugin under `plugins/` publishes its own skills, and the plugin name becomes the command prefix — the `writing` plugin gives you `/writing:email` and `/writing:tempering`.

```
.claude-plugin/marketplace.json   # marketplace: misoto22
plugins/
  writing/                        # plugin: writing
    .claude-plugin/plugin.json
    shared/                       # reference material both skills read on demand
    skills/
      email/
      tempering/
```

Shared material lives inside the plugin that uses it. A plugin is copied to a cache directory on install, so nothing outside its own directory is available at runtime — a plugin can never reference `../`. Two plugins needing the same reference file each carry a copy.

## Published skills

| Skill | Command | Purpose | Version |
| --- | --- | --- | ---: |
| [email](plugins/writing/skills/email/SKILL.md) | `/writing:email` | Draft policy-aware email or send exact validated artifacts with Sent-message readback verification. | 0.1.0 |
| [tempering](plugins/writing/skills/tempering/SKILL.md) | `/writing:tempering` | Rewrite a blunt or frustrated workplace message into three registers without losing the request. | 0.1.0 |

## Install

Claude Code, from GitHub:

```bash
claude plugin marketplace add Misoto22/skills
```

```bash
claude plugin install writing@misoto22
```

From a local clone, substitute `claude plugin marketplace add .` for the first command.

Agent Skills-compatible clients can install an individual skill with the pinned CLI used by CI:

```bash
npx --yes skills@1.5.20 add . --skill email
```

That creates a copied installation. It does not update automatically when the repository changes; rerun the command to refresh it.

For claude.ai and Cowork, download the `.skill` files attached to a [release](https://github.com/Misoto22/skills/releases) and upload them. Each archive carries its own copy of the plugin's `shared/` directory, so an uploaded skill is self-contained.

Maintainers who want editable local installations may run `bash scripts/link-skills.sh`. The script links only published skill directories, never overwrites real files or directories, and stops on conflicts.

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
python3 scripts/package-skill.py plugins/writing/skills/email dist
```

Tagging `v*` builds a `.skill` for every published skill and attaches them to a GitHub Release.

The repository contains no transport credentials and does not implement SMTP. License: [MIT](LICENSE).
