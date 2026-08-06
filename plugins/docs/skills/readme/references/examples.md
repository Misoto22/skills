# Worked examples

Three cases: rewriting a bloated README, building one from scratch for a project with no hero image, and an audit that does not rewrite anything.

## Contents

1. Rewrite — a bloated README
2. From scratch — a CLI tool
3. Audit — reporting without rewriting

---

## 1. Rewrite — a bloated README

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

## 2. From scratch — a CLI tool

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

## 3. Audit — reporting without rewriting

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
