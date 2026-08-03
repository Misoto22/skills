# skills

Portable, configurable agent skills for reliable everyday work. The repository is a monorepo: every release-ready skill lives under `skills/`, while future drafts and deprecated material stay outside the published tree.

## Published skills

| Skill | Purpose | Version |
| --- | --- | ---: |
| [email](skills/email/SKILL.md) | Draft policy-aware email or send exact validated artifacts with Sent-message readback verification. | 0.1.0 |

## Install

From a clone of this repository, Agent Skills-compatible clients can install the email skill with the pinned CLI used by CI:

```bash
npx --yes skills@1.5.20 add . --skill email
```

This creates a copied installation. It does not update automatically when the repository changes; rerun the install command to refresh it.

Claude Code users can register the local marketplace and install the curated plugin:

```bash
claude plugin marketplace add .
claude plugin install skills@skills
```

Maintainers who need editable local installations may run `bash scripts/link-skills.sh`. The script links only published skill directories, never overwrites real files or directories, and stops on conflicts.

## Use email

Copy [`skills/email/policy.example.json`](skills/email/policy.example.json) to `.agents/email-policy.json` in a project and replace the reserved example identity. Draft is always the default; automated send remains disabled until a narrow local scope is explicitly configured. See [docs/email.md](docs/email.md).

## Development

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate-repository.py
bash scripts/list-skills.sh
python3 scripts/package-skill.py skills/email dist
```

The repository contains no transport credentials and does not implement SMTP. License: [MIT](LICENSE).
