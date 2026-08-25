# README

A README answers three questions for someone who has never seen the repository: what is this, can I run it, and where do I go next. Everything else is a distraction from those three.

## Canonical shape

Follow this order. Sections that do not apply are dropped, and the order does not change.

A heading may take the word the project's own readers scan for, as long as it keeps its slot and its job: a library's Features may be Skills or Commands, and Getting Started is Install for something you distribute rather than clone. Renaming to sound different is churn; renaming to match the artefact is the point.

```
# <Project Name>

<div align="center">

<img alt="<project>" src="<hero image URL>" />

<br />

**<Two or three words. Who or what this is.>**

<The sentence: what it does, and what it runs on.>

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

`---` separates every section. Headings are `###`, never `##` — the `#` title is the only thing above them. See [skeleton.md](skeleton.md) for the full copy-pasteable version.

The centred sentence is the same one in the forge's About field and in the package manifest. Settle it once and paste it three times.

## Use what GitHub renders natively

GitHub strips CSS and JavaScript, so the page has four levers and no others.

- **A hero image is the only real design surface.** See [banner.md](banner.md).
- **Alerts** — `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]` — render with an icon and a coloured rule. Use one for the constraint a reader would otherwise miss, not for emphasis; three alerts on a page means none of them signals anything.
- **`<details>`** collapses a section that only some readers need. Install routes, one per agent, are the usual case: the reader takes their own and never scrolls the rest.
- **`mermaid` fences** render as diagrams. Use one where a relationship is the point — a tree of directories is not; marketplace to plugin to command is. Keep node labels to `<br/>`, since GitHub disables HTML labels and anything else prints literally.

Cap the page at two screens of scrolling before the first `<details>`. Long tables wrap badly at GitHub's content width — keep any row under about 90 characters, and if it will not fit, it was prose.

Centred text is for one line. A centred sentence past about 70 characters wraps, and a wrapped centre leaves a stranded last line under the fold of the block. Cut it to one line or left-align it.

## Section rules

**Features.** Bullets, each `**Term** — what it does`. The term is the thing a user would search for, not a category. Parenthesise the concrete handle where one exists: a route, a shortcut, an endpoint.

> - **Command palette** (Cmd+K) for quick navigation
> - **Contact form** sent server-side via Cloudflare Email Service (rate-limited `POST /api/contact`)

The Features list and the topics set are drawn from the same reading of the repository, and they should not contradict each other. A feature nobody would search for is not a topic; a topic that names something the Features list does not mention is worth checking.

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

## What to cut

Read the existing README and delete before adding. Most stale READMEs are long, not wrong.

- A table of contents. GitHub renders one from the headings.
- Badges for anything that is not a primary technology: no download counts, no "PRs welcome", no code-style badges.
- Screenshots of terminal output.
- A licence section that repeats `LICENSE` — one line at the bottom, or nothing.
- Contribution instructions that belong in `CONTRIBUTING.md`.
- A security-reporting paragraph that belongs in `SECURITY.md`.
- Roadmaps, changelogs, and acknowledgements — each has its own file.
- Any section that has not been true for two releases.

## Look at the rendered page

Markdown that reads fine as source can render badly, and that class of defect is invisible in a diff. Open `https://github.com/<owner>/<repo>` before calling a README done.

- **Every image loads.** A broken icon is the loudest thing on a page. Check the `<img>` reports a non-zero `naturalWidth`, not merely that the file exists.
- **Nothing centred has wrapped.** Measure the rendered text, not the source: a line of links is 128 characters of markdown and 29 characters on the page.
- **No table has wrapped mid-cell** at GitHub's content width.
- **Each `mermaid` fence produced a diagram.** GitHub renders it into a sandboxed `viewscreen` iframe, so the original `<pre lang="mermaid">` stays in the DOM inside `render-plaintext-hidden` — that leftover is the fallback copy, not a failure. Check the file page, `/blob/<branch>/README.md`: the repository home page reports the iframe at zero width whether or not the diagram is fine, so a measurement taken there proves nothing. Compare against another branch before believing any layout number.
- **Both themes.** A hero tuned for one is unreadable in the other.

An empty `<summary>` in the DOM is normally GitHub's own control on a diagram, not something you wrote.
