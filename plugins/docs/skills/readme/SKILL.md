---
name: readme
description: Use when writing, restructuring, auditing, or polishing a repository README — creating one for a new project, rewriting one that has gone stale or bloated, checking whether it tells a newcomer what they actually need, or bringing an inherited repository in line with the house style. Triggers on 写个 readme, 更新一下 readme, readme 太乱了, readme 写得怎么样, 帮我整理 readme, write a readme, polish the readme, the readme is out of date, does this readme make sense. Not for API reference documentation, changelogs, contribution guides, blog posts, or marketing landing pages.
license: MIT
metadata:
  version: "0.9.1"
---

# Readme

A README answers three questions for someone who has never seen the repository: what is this, can I run it, and where do I go next. Everything else is a distraction from those three.

## When a request names several repositories

Treat every explicitly named repository as its own scope. Record its exact path
or URL, README target, available evidence, and verification state before
editing. If a name cannot be resolved to one repository, ask; never widen the
scope by searching an unspecified parent directory.

Inspect, write, and render-check independent repositories concurrently when the
host supports concurrent work. Keep their commands, versions, deployment facts,
assets, and reader language separate unless the user supplies evidence that a
fact is shared. An inaccessible or blocked repository does not delay safe work
on another one.

Give one combined handoff with a clearly labelled result for each repository:
changed files, evidence and rendering checks, then any remaining blocker. A
single successful README never stands in for the rest.

## Read the repository before writing a line

Never describe a project from its name. Every claim in the output must come from a file you read.

| To write | Read |
|---|---|
| Tech stack, versions | `package.json`, `pyproject.toml`, `Cargo.toml`, lockfile |
| Getting started | the task runner (`justfile`, `Makefile`, `package.json` scripts), `.env.example` |
| Project structure | the actual tree, two levels deep |
| Features | routes, entry points, CI workflow names — not the previous README |
| Deployment | `.github/workflows/`, `compose.yaml`, `Dockerfile` |

Where a fact is unavailable, leave a bracketed placeholder — `[Node.js 24+]`, `[Module A]` — for the author to complete. An invented version number is worse than a blank.

A placeholder belongs in prose, never inside an attribute that renders. `src="[hero image URL]"` does not read as a note to the author; it renders as a broken-image icon, as the first thing on the page. When an asset does not exist, drop the element.

## Canonical shape

Follow this order. Sections that do not apply are dropped, and the order does not change.

A heading may take the word the project's own readers scan for, as long as it keeps its slot and its job: a library's Features may be Skills or Commands, and Getting Started is Install for something you distribute rather than clone. Renaming to sound different is churn; renaming to match the artefact is the point.

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

## Use what GitHub renders natively

GitHub strips CSS and JavaScript, so the page has four levers and no others.

- **A hero image is the only real design surface.** Commit it to the repository rather than hotlinking, and serve both themes with `<picture>` + `(prefers-color-scheme: dark)`. An SVG stays sharp and diffs as text. Place its text at explicit coordinates and left-anchored — `text-anchor` is not honoured by every renderer, and a label clipped at the edge is worse than a plain one.
- **Alerts** — `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]` — render with an icon and a coloured rule. Use one for the constraint a reader would otherwise miss, not for emphasis; three alerts on a page means none of them signals anything.
- **`<details>`** collapses a section that only some readers need. Install routes, one per agent, are the usual case: the reader takes their own and never scrolls the rest.
- **`mermaid` fences** render as diagrams. Use one where a relationship is the point — a tree of directories is not; marketplace to plugin to command is. Keep node labels to `<br/>`, since GitHub disables HTML labels and anything else prints literally.

Cap the page at two screens of scrolling before the first `<details>`. Long tables wrap badly at GitHub's content width — keep any row under about 90 characters, and if it will not fit, it was prose.

Centred text is for one line. A centred sentence past about 70 characters wraps, and a wrapped centre leaves a stranded last line under the fold of the block. Cut it to one line or left-align it.

## Look at the rendered page

Markdown that reads fine as source can render badly, and that class of defect is
invisible in a diff. Open `https://github.com/<owner>/<repo>` before calling a
README done.

- **Every image loads.** A broken icon is the loudest thing on a page. Check the `<img>` reports a non-zero `naturalWidth`, not merely that the file exists.
- **Nothing centred has wrapped.** Measure the rendered text, not the source: a line of links is 128 characters of markdown and 29 characters on the page.
- **No table has wrapped mid-cell** at GitHub's content width.
- **Each `mermaid` fence produced a diagram.** GitHub renders it into a sandboxed `viewscreen` iframe, so the original `<pre lang="mermaid">` stays in the DOM inside `render-plaintext-hidden` — that leftover is the fallback copy, not a failure. Check the file page, `/blob/<branch>/README.md`: the repository home page reports the iframe at zero width whether or not the diagram is fine, so a measurement taken there proves nothing. Compare against another branch before believing any layout number.
- **Both themes.** A hero tuned for one is unreadable in the other.

An empty `<summary>` in the DOM is normally GitHub's own control on a diagram,
not something you wrote.

## Section rules

**Features.** Bullets, each `**Term** — what it does`. The term is the thing a user would search for, not a category. Parenthesise the concrete handle where one exists: a route, a shortcut, an endpoint.

> - **Command palette** (Cmd+K) for quick navigation
> - **Contact form** sent server-side via Cloudflare Email Service (rate-limited `POST /api/contact`)

**Tech Stack.** Two columns: a bold category on the left, the actual choices joined by ` · ` on the right, with versions. Categories that carry no decision are dropped.

Markdown cannot express a headerless table — `| | |` renders as a visible empty row above the first entry — so write this one as HTML, where a `<tr>` of `<td>` needs no header. Backticks do not render inside a block-level HTML table; use `<code>`.

> ```html
> <table>
> <tr><td><b>Framework</b></td><td>Next.js 16 · Turbopack</td></tr>
> <tr><td><b>Testing</b></td><td><code>vitest</code> · Playwright (E2E)</td></tr>
> </table>
> ```

Every other table on the page has real headers and stays markdown.

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

**Getting Started.** One fenced block a reader can paste end to end, in the order they would run it. Document the shortest command that works, not the one you run in CI: flags that suppress prompts (`--yes`, `-y`, `--all`) exist for automation, and pasting them into a README hands every reader a silent install instead of the tool's own interactive one. Give the scripted form straight after, written out as its own block rather than described as a list of flags — a reader in CI needs to paste it, and a sentence naming three flags is not something anyone can paste. Then a bold **Prerequisites** line with exact minimum versions. Then the task runner's own commands, in a plain fence with aligned descriptions — not a bulleted list.

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

**The README's language is the repository's, not the conversation's.** Report back to the user in whatever language they are writing in, but write the file in the language its existing prose, code comments, and commit history already use. Ask only when the repository has no prose to read. A README rewritten into the language of whoever happened to request it is a README the next contributor cannot maintain.

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

1. Does the first screen render — every image loading, nothing centred wrapped?
2. Does the first screen say what this is and what it runs on?
3. Can a newcomer get it running from the Getting Started block alone?
4. Does every command still exist in the task runner?
5. Does every version match the lockfile?
6. Is anything described that no longer ships?

Report what fails with the line, and what the fix is. Do not rewrite unless asked.

## Worked examples

See [examples.md](references/examples.md) for a full before-and-after of a bloated README, a from-scratch build for a CLI tool with no hero image, and an audit report.
