# Worked examples

Four cases: a full seven-pass polish of a neglected repository, rewriting a bloated README, building one from scratch for a project with no hero image, and an audit that writes nothing.

## Contents

1. Full polish — a neglected repository
2. Rewrite — a bloated README
3. From scratch — a CLI tool
4. Audit — reporting without rewriting

---

## 1. Full polish — a neglected repository

`acme/supertask`: a working self-hosted task tracker, public for two years, with a README that is one paragraph and nothing else beside it.

**The plan table, printed before anything is written:**

> **Polish `acme/supertask` — 7 passes**
>
> | Pass | Target | Finding | Action |
> |---|---|---|---|
> | readme | `README.md` | 14 lines; no install, no stack, no structure | rewrite |
> | banner | — | no asset anywhere in the tree | skip: nothing to wire up |
> | license | `LICENSE` | absent; `Cargo.toml` says `license = "MIT"` | add MIT |
> | security | `SECURITY.md` | absent; repository is public | add |
> | contributing | `CONTRIBUTING.md` | absent; 11 merged pull requests from 6 people | add |
> | description | forge About | empty | set |
> | topics | forge topics | 0 of 20 | set 6 |

**The sentence**, settled first and used in three places:

> Self-hosted task tracker — Rust API, Postgres, htmx front end

It goes into the README's centred block, the forge's About field, and `Cargo.toml`'s `description`, which held `"supertask"` and now holds the sentence.

**Licence.** `Cargo.toml` declared MIT and no file existed. One declaration, no conflict, so the pass writes the canonical MIT text with `Copyright (c) 2023 [copyright holder]` — 2023 from the first commit, the holder left as a placeholder because neither the manifest's `authors` field nor the commit history names a person or organisation unambiguously. That placeholder is called out in the handoff rather than filled in.

**Security.** Private vulnerability reporting could not be confirmed as enabled from the CLI, so the file links the advisory page and the handoff carries the caveat. No email address was invented. No supported-versions table: the project has one branch.

**Contributing.** The commands came out of `.github/workflows/ci.yml` verbatim — `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test`. `git log --format=%s -50` showed 43 of 50 subjects in Conventional Commits form, so the file names that convention rather than inventing one.

**Banner.** Skipped, and reported as skipped. There is no asset to commit, and drafting one is brand work rather than layout. The README opens with the centred sentence and the badge row instead, and reads fine.

**Topics**, printed for confirmation before sending, then sent:

> `rust` · `postgresql` · `htmx` · `task-management` · `self-hosted` · `cli`

Six, not sixteen. `supertask` was dropped — the repository already matches on its own name. `well-tested` was dropped — nobody searches for it.

**The handoff:**

> **`acme/supertask` — 6 passes done, 1 skipped**
>
> Written: `README.md` (14 → 96 lines), `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `Cargo.toml` (`description`).
> Forge: About set; 6 topics set.
> Skipped: banner — no asset in the tree, and drawing one is a separate job.
>
> **Needs you:** `LICENSE` line 3 holds `[copyright holder]`. And confirm private
> vulnerability reporting is enabled under Settings → Security, or `SECURITY.md`
> links a form that will not open.
>
> Rendered check: README opens correctly in both themes, no centred line wraps,
> no table wraps mid-cell.

**Note**: the two things this handoff does that a finished-looking report would not — it names the skipped pass and its reason, and it hands back the one placeholder rather than filling it with a guessed name. Both are the point. A polish that quietly invents a copyright holder has created a false legal claim to save the author one line of typing.

---

## 2. Rewrite — a bloated README

**Before** (opening 20 lines of a 400-line file):

> # 🚀 SuperTask ✨
>
> Welcome to SuperTask, a blazing-fast, modern, and delightful task management
> solution built with cutting-edge technology! 🎉
>
> ## Table of Contents
>
> - [Introduction](#introduction)
> - [Features](#features)
> - [Installation](#installation)
> - [Usage](#usage)
> - [Contributing](#contributing)
> - [Roadmap](#roadmap)
> - [License](#license)
>
> ## Introduction
>
> In today's fast-paced world, staying organised is more important than ever.
> SuperTask was born out of a frustration with existing tools that are either
> too simple or too complex…

**Reading**: 400 lines, and the first screen contains no fact. A newcomer still does not know what it runs on or how to start it. Length is the defect, not accuracy.

**After** (first screen):

> # SuperTask
>
> <div align="center">
>
> <img alt="SuperTask" src="[hero image URL]" />
>
> <br />
>
> **Task management for teams**
>
> A self-hosted task tracker — Rust API, Postgres, htmx front end.
>
> <br />
>
> [Documentation](https://supertask.dev) · [Report Issue](https://github.com/acme/supertask/issues)
>
> <br />
>
> [![Rust](https://img.shields.io/badge/Rust_1.84-000?logo=rust&logoColor=fff)](https://www.rust-lang.org/)
> [![PostgreSQL](https://img.shields.io/badge/PostgreSQL_17-4169E1?logo=postgresql&logoColor=fff)](https://www.postgresql.org/)
>
> </div>
>
> ---
>
> ### Features
>
> - **Boards and swimlanes** with drag-and-drop ordering
> - **Recurring tasks** — cron expressions, evaluated server-side
> - **Webhooks** on every state transition (`POST /api/v1/hooks`)
> - **Single binary** — no runtime dependency beyond Postgres

**What was cut and why**: the emoji title (it breaks search and copy-paste), the table of contents (GitHub generates one), the Introduction (three paragraphs that never state a fact), the roadmap (belongs in issues), the contribution section (belongs in `CONTRIBUTING.md`). 400 lines became 90.

**Note**: "blazing-fast, modern, and delightful" was deleted rather than rewritten. There is no accurate version of it. The badge row does the same job with facts — a reader who sees `Rust 1.84` has learned more than any adjective could tell them.

---

## 3. From scratch — a CLI tool

No hero image, no live site. The centred block still earns its place.

**Reading of the repository**: `Cargo.toml` gives the name, version, and edition; `justfile` gives the task list; `src/main.rs` gives the subcommands; `.github/workflows/release.yml` shows binaries published per tag.

> # tally
>
> <div align="center">
>
> **Line counting that understands your repository**
>
> A single-binary code counter that reads `.gitignore`, groups by language, and diffs two revisions.
>
> <br />
>
> [Report Issue](https://github.com/acme/tally/issues)
>
> <br />
>
> [![Rust](https://img.shields.io/badge/Rust_1.84-000?logo=rust&logoColor=fff)](https://www.rust-lang.org/)
>
> </div>
>
> ---
>
> ### Features
>
> - **Respects `.gitignore`** and nested ignore files, without a flag
> - **Diff mode** (`tally diff HEAD~10 HEAD`) — lines added and removed per language
> - **JSON output** (`--format json`) for piping into a dashboard
> - **No configuration** — language detection ships with the binary
>
> ---
>
> ### Tech Stack
>
> | | |
> |:--|:--|
> | **Language** | Rust 1.84 (edition 2024) |
> | **CLI** | clap 4 · indicatif |
> | **Testing** | cargo test · insta (snapshot) |
> | **Release** | GitHub Actions — binaries per tag, x86_64 and aarch64 |
>
> ---
>
> ### Getting Started
>
> ```bash
> cargo install tally
> tally                       # current directory
> tally diff HEAD~10 HEAD     # what changed
> ```
>
> **Prerequisites** — Rust 1.84+ to build from source; the released binaries need nothing.
>
> **Common tasks** — `just` lists everything
>
> ```
> just build        Release build
> just test         cargo test + snapshot review
> just lint         clippy, warnings denied
> ```

**Note**: the Getting Started block opens with the install command a user actually runs, not with `git clone`. Clone-first is right for a site you deploy and wrong for a tool you install. Choose by asking what the reader came here to do.

---

## 4. Audit — reporting without rewriting

Asked "is this README any good?", answer against the checklist and stop at the first failure. Do not produce a rewrite.

> **README audit — 4 findings, 2 blocking**
>
> **1. Getting Started does not work** (blocking, line 78)
> `npm run dev` — `package.json` has no `dev` script. The scripts block has `start`
> and `dev:watch`. A newcomer's first command fails.
>
> **2. Versions are two majors stale** (blocking, lines 44–52)
> Tech Stack says React 17 and Node 16. `package.json` pins React 19, and
> `.nvmrc` says 22.
>
> **3. Describes a feature that no longer ships** (line 31)
> "**Offline mode** — full functionality without a connection". The service worker
> was removed in `a41f0c2` (March). Delete the bullet.
>
> **4. First screen states nothing** (line 3)
> Opens with "A modern solution for managing your workflow." A reader still does
> not know the language, the runtime, or whether it is a library or a service.
> Replace with one sentence naming both.
>
> Not raised: the table of contents and the four status badges are noise, but they
> mislead no one. Worth cutting when you next touch the file.

**Note**: findings are ordered by whether they waste a reader's time, not by position in the file. A command that fails outranks a paragraph that is merely empty. The last line separates "wrong" from "untidy" so the author can act on the first four and ignore the rest.

### The same audit, all seven passes

Asked "is this repo presentable?" rather than about the README alone, the report is the plan table with a finding per row and no Action column, because nothing is going to be done.

> **`acme/supertask` — presentable? No. 3 blocking.**
>
> **1. `LICENSE` and `package.json` disagree** (blocking)
> `LICENSE` is Apache-2.0. `package.json` line 7 says `"license": "MIT"`. Both have
> been in the tree since 2022, so neither is obviously the newer intent. This is
> yours to resolve — I will not pick one.
>
> **2. `SECURITY.md` points at a disabled feature** (blocking)
> It links `/security/advisories/new`. Private vulnerability reporting is off for
> this repository, so that link 404s for a reporter. Either enable it under
> Settings → Security, or replace the link with a contact you will read.
>
> **3. Getting Started does not work** (blocking, `README.md` line 78)
> `npm run dev` — `package.json` has no `dev` script. It has `start` and `dev:watch`.
>
> **4. About field is two rewrites stale**
> Reads "experimental task API". It has shipped a front end and a CLI since.
>
> **5. Topics describe the old stack** (`python`, `flask`, `python2`)
> The repository has been Rust since 2023. These send people to the wrong project.
>
> Not raised: no banner, and no `CONTRIBUTING.md`. Neither is a defect — the
> repository has had two outside pull requests in three years, and a contributing
> guide nobody needs is a file to keep current for nothing.

**Note**: the licence conflict outranks the broken install command, even though fewer people hit it, because a reader cannot resolve it for themselves and it decides whether they may use the code at all. And the last line is doing real work: an audit that lists every absent file as a finding trains the reader to ignore the list.
