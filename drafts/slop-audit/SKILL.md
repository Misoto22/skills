---
name: slop-audit
description: Audit how far a repository lets agents be trusted to write code unreviewed — whether agent corrections are enforced as lint, type, boundary, or verification checks instead of prose — and score it on ten checks from the "All Code Is Slop (Except Mine)" trust pyramid. Use when asked for a slop audit, agent-readiness or trust audit, 自我审查项目, 审一下这个项目对 agent 友不友好, or which corrections should become lint rules. Not for reviewing a single change or pull request, and not for fixing the gaps it finds.
---

# Slop audit

A read-only audit. The question it answers: **which lessons in this repository are _enforced_, and which still live only in prose?** A lesson is _enforced_ when a check that CI runs fails on a violation. A rule written in `AGENTS.md`, a comment, or a skill is prose, however well written.

The trust pyramid, bottom first, sets the order of investment and of this audit:

1. **Code**: API design and architecture that make the wrong thing hard to write.
2. **Static checks**: lint rules, types, import boundaries, tests.
3. **Verification**: runtime (run the app, capture evidence), property-based, formal.
4. **Prose**: rules, skills, `AGENTS.md`, kept for what needs judgement.
5. **Automation** (outer loop): worth building only on top of 1–3.

The audit changes no code, config, or rules file. Every gap becomes a proposal in the report.

## Scores

Every check gets exactly one of:

| Score | Meaning |
|---|---|
| `2` | _Enforced_: the check exists, CI runs it, and it passes on the default branch or holds a baseline that may only shrink (a _ratchet_). |
| `1` | Partial: configured but not run by CI, enforced for some cases only, or explicit and consistent but unchecked. |
| `0` | Missing, or prose only. |
| `n/a` | Does not apply to this repository; say why in one line. |
| `not assessed` | Could not be judged within the check's bounds; say what would settle it. |
| `blocked` | An input was unreachable (for example no `gh` access); name it. |

Evidence rules that apply to every check:

- A score without evidence is `0`. Evidence is `file:line`, or the exact command and its output.
- A CI-run AST or architecture test counts as lint.
- When you cannot run an enforcer locally (no environment, and installing is out of bounds), cite the latest green run of the default branch (`gh run list --branch <default> --workflow <file> -L 5 --json conclusion,headSha`) and mark the finding "not run locally".
- Count before you claim. Record the raw count (`rg -c`) **and** your estimate of true misuses, since raw counts include legitimate uses.

## Steps

### 1. Reconnaissance

Read `AGENTS.md` / `CLAUDE.md` / `.claude/rules/`, the CI workflows, lint, type and test configuration, and package manifests. Record:

- languages and frameworks, and the number of source files;
- the linters, type checkers, test runners and import-boundary tools **already installed**. Proposals reuse these first;
- each lint and test command with the **CI job name** that runs it, or "not in CI";
- the default branch and whether `gh` can reach the remote;
- any machinery the repository already uses to judge itself: a rule register with statuses, a census, a findings ledger, a rules contract with derived enforcement tiers, or repository audit skills. Its counts and statuses become evidence; you check them against reality instead of re-deriving them.

Done when every language has a named lint command and test command, each marked with its CI job or "not in CI", and the self-judging machinery is listed (or recorded as absent).

### 2. Run the ten checks

Run every check in [`references/checks.md`](references/checks.md), in order. Each check states its own bounds; stop at the bound and score what you have rather than reading further. When the repository has more than 500 source files, give checks 1–4 and 5–8 to two parallel read-only subagents with the reconnaissance notes, and run 9–10 yourself.

For each check, record the score, the evidence, at most three gaps ranked by recurrence, and one proposal: the smallest change that raises the score, naming the file to change, an installed tool, and the check that would enforce it.

Done when all ten checks carry a score from the table above and evidence or a one-line reason.

### 3. Report

Fill [`references/report-template.md`](references/report-template.md) and give it in the reply. Save it to a file only when the user asks; then, if the repository has `docs/audits/`, save it there as `slop-audit-YYYY-MM-DD.md`.

Lead with the three proposals that remove the most recurring corrections, each sized in time (for example, "about 30 minutes: one ruff `banned-api` entry plus fixing the 12 existing violations").

Done when every gap has a proposal and every proposal names a file to change and the check that would enforce it.

## While auditing

- Stay read-only: proposals go in the report and the user decides what to build. Read-only `git` and `gh` commands are in bounds; installs, formatters with `--fix`, migrations and branch switches are not.
- Where the repository has its own audit skills or loops (security, backend, UI, a rules-register review), point to them for depth and keep this audit to the ten checks.
