---
name: readme
description: Use when writing, restructuring, auditing, or polishing a repository README — creating one for a new project, rewriting one that has gone stale or bloated, checking whether it tells a newcomer what they actually need, or bringing an inherited repository in line with the house style. Triggers on 写个 readme, 更新一下 readme, readme 太乱了, readme 写得怎么样, 帮我整理 readme, write a readme, polish the readme, the readme is out of date, does this readme make sense. Not for API reference documentation, changelogs, contribution guides, blog posts, or marketing landing pages.
license: MIT
metadata:
  version: "0.2.0"
---

# Readme

A README answers three questions for someone who has never seen the repository: what is this, can I run it, and where do I go next. Everything else is a distraction from those three.

## Read the repository before writing a line

Never describe a project from its name. Every claim in the output must come from a file you read.

| To write | Read |
|---|---|
| Tech stack, versions | `package.json`, `pyproject.toml`, `Cargo.toml`, lockfile |
| Getting started | the task runner (`justfile`, `Makefile`, `package.json` scripts), `.env.example` |
| Project structure | the actual tree, two levels deep |
| Features | routes, entry points, CI workflow names — not the previous README |
| Deployment | `.github/workflows/`, `compose.yaml`, `Dockerfile` |

Where a fact is unavailable, leave a bracketed placeholder — `[hero image URL]`, `[Node.js 24+]` — for the author to complete. An invented version number is worse than a blank.

## Canonical shape

Follow this order. Sections that do not apply are dropped, never reordered or renamed.

```
# <Project Name>

<div align="center">

<img alt="<project>" src="<hero image URL>" />

<br />

**<Two or three words. Who or what this is.>**

<One sentence: what it does, and what it runs on.>

<br />

[Live Site](<url>) · [Report Issue](<repo>/issues)

<br />

<one shields.io badge per primary technology, version pinned>

</div>

---

### Features
### Tech Stack
### Project Structure
### Getting Started
### Documentation
### Deployment
### <domain-specific sections, as many as the project earns>

---

<div align="center">
<sub>Built by <author></sub>
</div>
```

`---` separates every section. Headings are `###`, never `##` — the `#` title is the only thing above them. See [skeleton.md](references/skeleton.md) for the full copy-pasteable version.

## Section rules

**Features.** Bullets, each `**Term** — what it does`. The term is the thing a user would search for, not a category. Parenthesise the concrete handle where one exists: a route, a shortcut, an endpoint.

> - **Command palette** (Cmd+K) for quick navigation
> - **Contact form** sent server-side via Cloudflare Email Service (rate-limited `POST /api/contact`)

**Tech Stack.** A two-column table, `| | |` header with `|:--|:--|` alignment. Left column is a bold category, right column is the actual choices joined by ` · `, with versions. Categories that carry no decision are dropped.

> | **Framework** | Next.js 16 · Turbopack |
> | **Testing** | Vitest 4 · Playwright (E2E) · fast-check (property-based) |

**Project Structure.** A fenced tree, comments aligned in a column, one line per directory that a newcomer would need to open. Do not list every file. Annotate what lives there, not what the name already says.

> ```
> src/
> ├── app/
> │   ├── [locale]/           Locale-aware pages (en default, /zh for Chinese)
> │   └── api/                REST API routes (photos, blog, search-index)
> └── lib/
>     └── data/               Domain-split fetchers + Db→Frontend mappers
> ```

**Getting Started.** One fenced block a reader can paste end to end, in the order they would run it. Then a bold **Prerequisites** line with exact minimum versions. Then the task runner's own commands, in a plain fence with aligned descriptions — not a bulleted list.

**Deployment.** What triggers it, what it produces, where it lands, and a link to the full runbook. Never inline the runbook.

**Domain sections.** One per subsystem a reader would otherwise misunderstand — usually a boundary with another service. State what this repository owns and what it does not.

> Kioku is the sole Spotify client and credential owner. This site reads the stable
> `/api/v1/music/*` contracts, and needs no Spotify secret.

That last move is the one most READMEs miss. A reader who knows where the boundary is stops looking for credentials that were never here.

## Voice

**No marketing adjectives.** Blazing, seamless, powerful, robust, cutting-edge, beautiful, delightful, effortless. A README describes; a landing page sells. Strip them without replacement — the sentence is almost always better shorter.

| Before | After |
|---|---|
| A blazing-fast, modern web framework with a delightful developer experience | Next.js 16 · Turbopack |
| Powerful and flexible configuration options | Configuration lives in `config.toml` |

**No filler openers.** "Welcome to", "This project is a", "In today's world", "Have you ever wanted to". Start with the noun.

**State boundaries as facts.** "This site owns no database credential, schema, migration, or local Postgres lifecycle" is worth more than a paragraph of architecture prose, because it closes a question instead of opening one.

**Point at runbooks, do not inline them.** A README that contains the deployment procedure goes stale the first time the procedure changes. Link to the file that is maintained alongside the thing it documents.

**Separator is ` · `**, not `|` or `,`, when joining peer items on one line.

**Em dash for explanation** after a bold term. Not a colon.

**Every command must run as written.** Copy it from the task runner or the scripts block; do not paraphrase it.

## What to cut

Read the existing README and delete before adding. Most stale READMEs are long, not wrong.

- A table of contents. GitHub renders one from the headings.
- Badges for anything that is not a primary technology: no download counts, no "PRs welcome", no code-style badges.
- Screenshots of terminal output.
- A licence section that repeats `LICENSE` — one line at the bottom, or nothing.
- Contribution instructions that belong in `CONTRIBUTING.md`.
- Roadmaps, changelogs, and acknowledgements — each has its own file.
- Any section that has not been true for two releases.

## Audit mode

When asked whether a README is any good rather than to rewrite it, answer against these in order, and stop at the first that fails:

1. Does the first screen say what this is and what it runs on?
2. Can a newcomer get it running from the Getting Started block alone?
3. Does every command still exist in the task runner?
4. Does every version match the lockfile?
5. Is anything described that no longer ships?

Report what fails with the line, and what the fix is. Do not rewrite unless asked.

## Worked examples

See [examples.md](references/examples.md) for a full before-and-after of a bloated README, a from-scratch build for a CLI tool with no hero image, and an audit report.
