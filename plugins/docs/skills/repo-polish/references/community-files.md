# Community files

`LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, and the two that travel with them. Each exists to answer one question a stranger has, and each is worth writing only when the answer is real.

| File | The question it answers | Write it when |
|---|---|---|
| `LICENSE` | May I use this? | Always. Its absence is itself an answer, and rarely the intended one. |
| `SECURITY.md` | Where do I report a vulnerability that is not a public issue? | The repository is public. |
| `CONTRIBUTING.md` | What do I have to do for a patch to be accepted? | The repository accepts outside patches. |
| `CODE_OF_CONDUCT.md` | Who enforces behaviour, and how? | There is someone who will actually enforce it. |
| `.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md` | What do you need from me in this report? | Reports arrive missing the same field every time. |

---

## LICENSE

**Never choose the licence.** It is the owner's decision and it binds every downstream user. This pass makes an existing decision consistent; it does not make a new one.

### Reconcile first

Read every place the repository already declares one:

```
LICENSE  LICENSE.md  LICENCE  COPYING
package.json          .license
pyproject.toml        .project.license  or  [project] license
Cargo.toml            .package.license
plugin.json           .license
SPDX-License-Identifier: headers in source files
the README footer
```

- **All agreeing, file present** → nothing to write. Check the copyright line names a holder and a year that is not in the future.
- **All agreeing, file missing** → write the canonical text of that SPDX identifier verbatim. Never retype it from memory or summarise it; a licence with a reworded clause is a licence nobody can rely on.
- **Disagreeing** → stop and report both, with the file and line of each. Do not resolve it by picking the more permissive, the more common, or the more recently edited. Two declarations is a question for the owner.
- **Nothing declares one** → ask, with the shortlist below. Until answered, write nothing.

### A dependency can constrain the answer

A project cannot be licensed more loosely than a library it links. A GPL or AGPL dependency pulls the whole work along with it; a permissive one does not. Where the manifest holds a copyleft dependency and the declared licence is permissive, that is a real conflict, not a formatting one — report it in the same breath as the disagreement case.

### The shortlist, and what each costs

| SPDX | What a user may do | What it costs you |
|---|---|---|
| `MIT` | Anything, including selling it | Nothing beyond keeping your notice. No patent grant. |
| `Apache-2.0` | Anything, with an explicit patent grant | Longer file; users must state what they changed. |
| `BSD-3-Clause` | Anything | Like MIT, plus nobody may use your name to endorse their fork. |
| `MPL-2.0` | Anything, including linking from closed source | Modified *files* stay MPL; the rest of their program need not. |
| `GPL-3.0-or-later` | Anything, if they pass the same terms on | Anyone distributing a derived work must offer its source. |
| `AGPL-3.0-or-later` | The same | Also triggered by running a modified version as a network service. |
| `CC0-1.0` | Anything, no attribution at all | Public-domain dedication; uncertain in some jurisdictions, no patent grant. |

For a repository that is prose, data, or images rather than code, a code licence fits badly — the Creative Commons family is the usual answer, and it is still the owner's call.

Choosing nothing is also a decision, and a legible one: "All rights reserved. Not licensed for reuse." in the README says what silence only implies.

### The copyright line

```
Copyright (c) [year] [holder]
```

Year from the first commit — `git log --reverse --format=%ad --date=format:%Y` and take the first line — or the current year for a new repository. A range is unnecessary; most licences do not require one. The holder is the person or organisation in the manifest's author field or the repository owner. Where neither is knowable, leave the placeholder; an invented copyright holder is a false legal claim.

---

## SECURITY.md

The whole job is a private channel that exists. Everything else is optional, and most of it is a promise.

```markdown
# Security Policy

## Reporting a vulnerability

Please do not open a public issue for a security problem.

Use [GitHub's private vulnerability reporting]([repo url]/security/advisories/new),
which opens a private thread visible only to the maintainers.

[Or: email [security contact]. — only when the owner supplied an address.]

Include what you can: the version or commit, what an attacker can do with it, and
the shortest way to reproduce it.

## Supported versions

| Version | Supported |
|---|---|
| [2.x]   | Yes |
| [1.x]   | No — [end-of-life date] |

## Scope

[What is deliberately not a vulnerability here: a demo credential in a fixture,
a deliberately vulnerable example, a dependency's own advisory.]
```

- **Link the repository's own advisory page**, `/security/advisories/new`, not GitHub's generic documentation. On GitLab, a confidential issue is the equivalent; name it and say how to mark one confidential.
- Private reporting has to be **switched on** in the repository's settings before that link works. Say so in the handoff if you cannot verify it is enabled — a policy pointing at a disabled feature is worse than no policy.
- **Never invent a contact address.** No `security@`, no personal mail, nothing derived from the owner's name or domain. Placeholder, or the GitHub channel alone.
- **Drop the supported-versions table** unless more than one line is genuinely maintained. A single-branch project inventing one is promising maintenance nobody agreed to.
- **Drop response times** unless the owner states them. "We aim to respond within 48 hours" from a solo maintainer is a promise broken in public.

---

## CONTRIBUTING.md

Write it only where outside patches are actually accepted. On a repository that does not take them, this file is a form nobody will fill in; one line in the README is the honest configuration.

````markdown
# Contributing

Thanks for taking the time. [One sentence: what kinds of change are welcome, and
what to open an issue about first.]

## Setup

See [Getting Started](README.md#getting-started). Nothing extra is needed to
develop this.

## Before you open a pull request

[Copied from the CI workflow, verbatim:]

```bash
[the lint command]
[the format command]
[the test command]
```

CI runs the same three, so a green local run is a green pull request.

## Commits and pull requests

[The convention the history actually uses — read it, do not assume it.]

- [Subject style, from `git log --format=%s -50`]
- [Branch naming, if the repository has one]
- One logical change per pull request.

## Where to ask

[Issues · Discussions · a link.]
````

- **Link the README's Getting Started; never restate it.** Two install paths drift within one release.
- **Copy the checks out of `.github/workflows/`, character for character.** If the workflow runs `uvx ruff check .`, the file says `uvx ruff check .` — not "run the linter". A contributor who runs what the file says and still fails CI will not come back.
- **Read the last fifty subjects before naming a convention.** `git log --format=%s -50` shows whether this project writes Conventional Commits, sentence-case subjects, or issue-number prefixes. Match what is there. Importing a convention the repository has never used makes every existing commit retroactively wrong.
- **Sign-off and CLA requirements are the maintainer's to state.** Do not add a DCO line because other projects have one.

## CODE_OF_CONDUCT.md

The standard answer is Contributor Covenant 2.1, adopted verbatim. Its one variable is the enforcement contact, and that is the whole reason to think before adding it: a code of conduct naming a contact nobody reads is worse than none, because it invites a report that will go unanswered. Add it when the owner names an enforcer, and not otherwise.

## Issue and pull-request templates

Worth adding once reports keep arriving missing the same field. Then the template asks for exactly that field and nothing else — a form long enough to be a chore suppresses the reports you wanted.

Keep them under `.github/`: `ISSUE_TEMPLATE/bug_report.md` with a `name` and `about` in its frontmatter, and `pull_request_template.md`, which takes no frontmatter and is inserted into the body as written.

`.github/FUNDING.yml` renders a Sponsor button and belongs to the owner, not to this pass. Never add it unprompted.
