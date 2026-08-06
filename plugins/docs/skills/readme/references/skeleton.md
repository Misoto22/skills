# Skeleton

Copy this, fill the placeholders, delete the sections the project has not earned. Bracketed placeholders stay in the output when the fact is unavailable — the author completes them.

````markdown
# [Project Name]

<div align="center">

<!-- Delete this block entirely if you have no hero image; a placeholder in src
     renders as a broken icon. Commit the asset, and serve both themes:
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">
  <img alt="[project]" src="assets/hero-light.svg" width="820">
</picture>

<br />
-->

**[Two or three words. Who or what this is.]**

[One sentence: what it does, and what it runs on.]

<br />

[Live Site]([url]) · [Report Issue]([repo]/issues)

<br />

[![Next.js](https://img.shields.io/badge/Next.js_16-000?logo=next.js&logoColor=fff)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript_6.0-3178C6?logo=typescript&logoColor=fff)](https://www.typescriptlang.org/)

</div>

---

### Features

- **[Term]** — [what it does]
- **[Term]** ([concrete handle: route, shortcut, endpoint]) — [what it does]

---

### Tech Stack

| | |
|:--|:--|
| **Framework** | [name version] · [tooling] |
| **Language** | [name version] |
| **Testing** | [runner] · [e2e] · [property-based] |
| **Deploy** | [where and how] |

---

### Project Structure

```
src/
├── [dir]/                  [what lives here]
│   └── [dir]/              [what lives here]
└── [dir]/                  [what lives here]
[top-level dir]/            [what lives here]
```

---

### Getting Started

```bash
git clone [repo url]
cd [project]
cp .env.example .env        # fill in credentials
[install command]
[dev command]               # → http://localhost:[port]
```

**Prerequisites** — [runtime version], [package manager version], [task runner]

**Common tasks** — `just` (or `just help`) lists everything

```
just dev          [description]
just lint         [description]     just typecheck   [description]
just test         [description]     just test-e2e    [description]
just build        [description]     just check       [description]
```

---

### Documentation

[Where the engineering docs live, one sentence, with a link. If none exist, drop this section.]

---

### Deployment

[What triggers it] — [what it produces], [where it lands]. See
[`[path to runbook]`]([path to runbook]) for the full runbook.

---

### [Domain section]

[What this repository owns, and — where a reader would otherwise go looking — what it does not.]

---

<div align="center">
<sub>Built by [author]</sub>
</div>
````

## Badge sources

One badge per primary technology, version pinned in the label, official brand colour, `logoColor` set for contrast. The pattern:

```
https://img.shields.io/badge/<Name>_<Version>-<hex>?logo=<slug>&logoColor=<fff|000>
```

Use `logoColor=000` on light brand colours (React `61DAFB`, Tailwind `06B6D4`), `fff` on dark ones. Underscores render as spaces. Look the slug up at [simpleicons.org](https://simpleicons.org).

No badges for build status, download counts, licence, "PRs welcome", or code style. They are noise on a personal or single-maintainer repository, and the CI section already says what runs.

## When there is no hero image

Drop the `<img>` and the `<br />` after it. Never leave the placeholder in `src` — it does not read as a note to the author, it renders as a broken-image icon at the top of the page. The centred block still works, and is better than a placeholder graphic. A CLI tool may reasonably open with a fenced sample of its own output instead — one screen, real output, no prompt characters.
