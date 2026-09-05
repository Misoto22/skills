---
name: repo-polish
description: Build or restore a repository's public face — README, hero banner, LICENSE, SECURITY.md, CONTRIBUTING.md, the forge's one-line About text, and its GitHub or GitLab topics — written from what the repository's own files say. Every pass runs unless flags narrow it. Use when asked to 装修一下仓库, 仓库装修, 美化仓库, 把开源文件补齐, 写个 readme, 加个 license, 补个安全策略, 设置仓库 topics, 仓库描述写一下, polish this repo, set the repo up properly, add a security policy, fill in the repository description, or tag a repository on GitHub. Not for API reference docs, changelogs, release notes, marketing landing pages, or the source code itself.
license: MIT
metadata:
  version: "0.16.0"
argument-hint: "[--readme] [--banner] [--license] [--security] [--contributing] [--description] [--topics] [--audit] [--dry-run]"
---

# Repo Polish

A repository's public face is seven artefacts, and they are one job because they all answer the same question for a stranger: what is this, may I use it, and where do I go next. Written separately they contradict each other — a README that says MIT beside a `LICENSE` that says Apache-2.0, a forge description two rewrites behind the first line of the README.

**Every pass runs by default.** With any of `--readme`, `--banner`, `--license`, `--security`, `--contributing`, `--description`, `--topics`, only those. `--audit` reports without writing. `--dry-run` stops after the plan table.

| Pass | Artefact | Reference |
|---|---|---|
| `--readme` | `README.md` | [readme.md](references/readme.md), [skeleton.md](references/skeleton.md) |
| `--banner` | the hero image the README opens with | [banner.md](references/banner.md) |
| `--license` | `LICENSE`, and the SPDX id agreeing everywhere | [community-files.md](references/community-files.md) |
| `--security` | `SECURITY.md` | [community-files.md](references/community-files.md) |
| `--contributing` | `CONTRIBUTING.md` | [community-files.md](references/community-files.md) |
| `--description` | the forge's one-line About text | [forge-metadata.md](references/forge-metadata.md) |
| `--topics` | GitHub topics · GitLab project topics | [forge-metadata.md](references/forge-metadata.md) |

## One sentence, said once

Before any pass writes, settle **the sentence**: what this is and what it runs on, in one line under about 120 characters. It is the same text in the README's centred block, in the forge's About field, and in the `description` of `package.json`, `pyproject.toml`, `Cargo.toml`, or a plugin manifest. Not paraphrases of each other — the same sentence.

That agreement is the whole reason these passes travel together. A reader meets the repository through whichever one their search returned, and three descriptions mean two of them are stale.

The same holds for the licence: one SPDX identifier, in `LICENSE` and in every manifest that declares one. Where they already disagree, say so and stop — see the licence pass.

## 0. Read the repository before writing a line

Never describe a project from its name. Every claim in the output must come from a file you read.

| To write | Read |
|---|---|
| The sentence, tech stack, versions | `package.json`, `pyproject.toml`, `Cargo.toml`, lockfile |
| Getting started | the task runner (`justfile`, `Makefile`, `package.json` scripts), `.env.example` |
| Project structure | the actual tree, two levels deep |
| Features | routes, entry points, CI workflow names — not the previous README |
| Deployment | `.github/workflows/`, `compose.yaml`, `Dockerfile` |
| Licence | `LICENSE`, manifest `license` fields, file headers |
| Contribution conventions | `git log --format=%s -50`, the CI workflow's own steps |
| Topics and About | everything above, plus what the forge already has set |

Where a fact is unavailable, leave a bracketed placeholder — `[Node.js 24+]`, `[Module A]` — for the author to complete. An invented version number is worse than a blank.

A placeholder belongs in prose, never inside an attribute that renders. `src="[hero image URL]"` does not read as a note to the author; it renders as a broken-image icon, as the first thing on the page. When an asset does not exist, drop the element.

Read what is already there before adding. Most stale repositories are over-decorated, not under-decorated — the pass that deletes a badge wall is doing as much work as the pass that writes a file.

## Print the plan, then work

Nothing is written until it is printed. One markdown table, never a fixed-width block — findings are written in the reader's language and any column width computed here is wrong in their terminal.

> **Polish `<repo>` — 7 passes**
>
> | Pass | Target | Finding | Action |
> |---|---|---|---|
> | readme | `README.md` | 412 lines, no runnable Getting Started | rewrite |
> | banner | `assets/hero-*.svg` | absent | draft · skip: reason |
> | license | `LICENSE` | absent; `package.json` says `MIT` | add MIT |
> | security | `SECURITY.md` | absent | add |
> | contributing | `CONTRIBUTING.md` | names `npm run check`, which is gone | fix |
> | description | forge About | empty | set |
> | topics | forge topics | 0 of 20 | set 8 |

Stop here on `--dry-run`.

**A pass with no evidence is skipped, not guessed.** Say which fact was missing. A skipped pass reported is worth more than a file full of placeholders.

**The two forge passes leave the repository.** `--description` and `--topics` write to a live public page, and no local diff records them. Print the exact values, and get a yes before sending them. The local passes are ordinary file edits and need no confirmation beyond the plan table.

## 1. README

The full house style is in [readme.md](references/readme.md): the canonical section order, what GitHub renders natively, the section-by-section rules, and the render check to run before calling it done. [skeleton.md](references/skeleton.md) is the copy-pasteable version.

In short: three questions — what is this, can I run it, where do I go next — in that order, `###` headings, `---` between sections, two screens before the first `<details>`, and every command copied from the task runner rather than paraphrased.

## 2. Banner

The hero image is the only real design surface GitHub gives you, and the only one worth spending on. [banner.md](references/banner.md) covers what it has to survive: two themes, a phone's width, and a renderer that honours less SVG than you expect.

Two rules override everything else there. **Commit the asset**; a hotlinked banner is someone else's uptime. **Drop the element when there is no asset**; a broken-image icon at the top of the page is worse than a page with no image, and worse than any placeholder you were tempted to leave in `src`.

Where the artwork itself has to be made rather than laid out, that is a brand job and a different skill — this pass sizes it, wires up the `<picture>` block, and checks it renders.

## 3. Licence

**Never choose a licence.** Which one a project carries is the owner's decision, with consequences this skill cannot weigh. What this pass does is make the existing decision consistent and legible:

1. Collect every declaration — `LICENSE`, `LICENSE.md`, manifest `license` fields, SPDX headers, what the README's footer claims.
2. All agreeing, file present → nothing to do. Confirm the copyright line names someone and a year that is not in the future.
3. All agreeing, file missing → write the full canonical text of that SPDX identifier, with the copyright holder and year filled from the manifest and `git log`.
4. **Disagreeing → stop and report both.** Do not pick the more permissive one, the more common one, or the one in the newer file. Two declarations is a question for the owner, not a formatting defect.
5. Nothing declares one at all → ask. State plainly that no licence means no permission to use the code, and offer the shortlist in [community-files.md](references/community-files.md) with one line each on what it costs. Do not write a file until answered.

The README carries one line at the bottom, or nothing. A licence section that restates `LICENSE` is one more copy to go stale.

## 4. Security policy

`SECURITY.md` exists to give someone holding a vulnerability a channel that is not a public issue. Everything else in it is optional.

- **Name a private channel that exists.** On GitHub, private vulnerability reporting is the default answer, and the file should say so and link to the repository's own advisory page. On GitLab, a confidential issue. An email address goes in only when the owner supplies one — never invent a contact.
- **Supported versions, only where they are real.** A table listing 2.x supported and 1.x not is useful. A single-branch project has no such table, and inventing one promises maintenance nobody agreed to.
- **Response expectations, only where they are honest.** "We aim to acknowledge within 90 days" from a solo maintainer is a promise that will be broken in public. Silence is better than an SLA nobody owns.
- **Say what is out of scope** where the repository has an obvious non-issue — a demo credential in a fixture, a deliberately vulnerable example.

Template in [community-files.md](references/community-files.md).

## 5. Contributing

Only write this file where the repository actually takes outside contributions. On one that does not, it is a form nobody will fill in, and `README` plus a line in the About field is the honest configuration.

Where it is warranted:

- **Link to the README's Getting Started; do not restate it.** Two install paths drift within a release.
- **Every check a pull request must pass, copied from CI.** Read `.github/workflows/`. If the workflow runs `uvx ruff check .`, the file says `uvx ruff check .` — not "run the linter".
- **The conventions the history actually uses.** `git log --format=%s -50` tells you whether this project writes Conventional Commits, sentence-case subjects, or issue-number prefixes. Match what is there. Do not import a convention the repository has never used.
- **Where to ask** — issues, discussions, or a link. One line.

`CODE_OF_CONDUCT.md` and the issue and pull-request templates under `.github/` belong to the same decision. Where the repository takes contributions and lacks them, offer them in the same pass and write them only on a yes; where it does not, leave all of it alone.

## 6. Forge description

The one-line About text, on the repository's own page and in every search result and list that names it. Use **the sentence** settled above, unchanged.

- GitHub's hard limit is 350 characters; the useful limit is far shorter, because a repository list truncates it. Under 120.
- Do not open with the repository's name. It is rendered directly above.
- No marketing adjectives, no trailing period on a fragment, no emoji as the first character.
- A link belongs in the website field beside it, not inside the sentence.

Commands, and the GitLab equivalents, are in [forge-metadata.md](references/forge-metadata.md).

## 7. Topics

Topics are how a stranger who does not know the repository exists finds it. That is the only test a candidate has to pass.

- **Terms someone would search**, not terms that describe the codebase to its author. `react` and `postgresql`, not `well-architected` or `personal-project`.
- **Ceiling 20 on GitHub**; eight to twelve is usually the honest count. A repository claiming twenty topics is claiming twenty audiences.
- **Lowercase, hyphenated, ≤50 characters each**, starting with a letter or digit — GitHub normalises anything else, so write them normalised and know what you sent.
- **Do not repeat the repository's own name**; it already matches on name.
- **Drop what is no longer true.** Read the existing set first; a `python2` topic on a repository that dropped it is worse than no topic.

Where the repository is a library or a plugin published to a directory, one topic is usually that directory's own convention. Read what comparable repositories in it use rather than inventing one.

## Voice

Every artefact this skill writes shares one voice. It is the same rule seven times: describe, do not sell.

**No marketing adjectives.** Blazing, seamless, powerful, robust, cutting-edge, beautiful, delightful, effortless. Strip them without replacement — the sentence is almost always better shorter.

| Before | After |
|---|---|
| A blazing-fast, modern web framework with a delightful developer experience | Next.js 16 · Turbopack |
| Powerful and flexible configuration options | Configuration lives in `config.toml` |

**No filler openers.** "Welcome to", "This project is a", "In today's world". Start with the noun.

**State boundaries as facts.** "This site owns no database credential, schema, migration, or local Postgres lifecycle" closes a question instead of opening one.

**Point at runbooks, do not inline them.** A file that contains a procedure goes stale the first time the procedure changes.

**Separator is ` · `**, not `|` or `,`, when joining peer items on one line. **Em dash for explanation** after a bold term, not a colon.

**Every command must run as written.** Copy it from the task runner or the workflow; do not paraphrase it.

**The repository's language, not the conversation's.** Report back to the user in whatever language they are writing in, and write the files in the language the repository's existing prose, code comments, and commit history already use. Ask only when there is no prose to read. A README rewritten into the language of whoever happened to request it is a README the next contributor cannot maintain.

Topics and the SPDX identifier are the two exceptions: both are machine-matched vocabularies and stay in their own form regardless of the repository's language.

## Audit mode

When asked whether a repository is presentable rather than to fix it, run the plan table and stop. Report per pass, worst first, with the line and the fix. Do not write anything.

Within the README pass, answer these in order and stop at the first that fails:

1. Does the first screen render — every image loading, nothing centred wrapped?
2. Does the first screen say what this is and what it runs on?
3. Can a newcomer get it running from the Getting Started block alone?
4. Does every command still exist in the task runner?
5. Does every version match the lockfile?
6. Is anything described that no longer ships?

Across the other passes, the failures worth reporting are: a licence that two files disagree about, a `SECURITY.md` naming a channel that does not exist, a `CONTRIBUTING.md` whose commands are gone, an empty or stale About field, and topics that describe something the repository no longer does.

## When a request names several repositories

Treat every explicitly named repository as its own scope. Record its exact path or URL, which passes apply, available evidence, and verification state before editing. If a name cannot be resolved to one repository, ask; never widen the scope by searching an unspecified parent directory.

Inspect, write, and render-check independent repositories concurrently when the host supports concurrent work. Keep their commands, versions, licences, deployment facts, assets, and reader language separate unless the user supplies evidence that a fact is shared. An inaccessible or blocked repository does not delay safe work on another one.

Give one combined handoff with a clearly labelled result for each repository: changed files, forge fields written, evidence and rendering checks, then any remaining blocker. A single successful repository never stands in for the rest.

## Worked examples

See [examples.md](references/examples.md) for a full seven-pass polish of a neglected repository, a rewrite of a bloated README, a from-scratch build for a CLI tool with no hero image, and an audit report.
