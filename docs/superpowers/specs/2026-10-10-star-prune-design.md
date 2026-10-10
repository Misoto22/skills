# Star Prune Skill Design

## Purpose

Add `star-prune` to the `github-account` plugin. Stars accumulate repositories that are archived, deprecated, or dormant, and they crowd out the ones still worth returning to. The skill finds those repositories, explains why each one was flagged, and unstars the ones the user confirms, with a backup that can re-star them.

The published command is `/github-account:star-prune`. `star-lists` already states that it does not star or unstar; this skill owns that boundary.

## Problem, with evidence

A read of a real account with 156 stars (2026-10-10) shows the signals GitHub exposes per starred repository through GraphQL: `isArchived`, `isDisabled`, `isLocked`, `isMirror`, `pushedAt`, `archivedAt`, `stargazerCount`, `description`, topics, and the edge field `starredAt`. Every flag the skill raises comes from these fields. Nothing is inferred from outside GitHub.

On that account the rules below flag 3 archived repositories, none disabled or described as deprecated, and 18 dormant ones (no push in more than two years). Half of the dormant ones are finished course material or roadmaps the owner keeps on purpose, which is why dormancy alone proposes `keep`, not `unstar`.

## Options considered

| Option | For | Against |
|---|---|---|
| A. A separate `star-prune` skill in `github-account` | One job per skill; its description can trigger on "clean up dead stars" without competing with list organizing; unstarring is a different risk from moving between lists | A second skill needs the shared GraphQL client and bootstrap, which means extracting `shared/` |
| B. A `prune` mode inside `star-lists` | No extraction | `star-lists` is already 120 lines of instructions; its description says it never unstars, and reversing that makes one skill own two risk levels |
| C. Prose-only skill that tells the agent which `gh` commands to run | No scripts to test | No backup, no verification, and no way to test the classification rules |

**Choice: A.** It keeps each skill's description honest about what it writes, and the extraction is the step the plugin README already anticipates for a second skill.

## Shared code

`plugins/github-account/shared/` gets the two pieces both skills need, vendored into each skill by `scripts/sync-shared.py`:

- `bootstrap.sh`: dependency, sign-in and scope checks, and the checksum-verified install of gh and uv. Each skill's `scripts/run.sh` becomes a thin wrapper that sources it and names its own Python entry point.
- `github_api.py`: the GraphQL runner and retry policy. Each skill adds its own queries and mutations on top.

`star-lists` behaviour does not change. Its tests keep passing unmodified apart from import paths.

## Classification

Each starred repository gets zero or more reasons, strongest first:

| Reason | Rule |
|---|---|
| `disabled` | `isDisabled` (GitHub took it down) |
| `archived` | `isArchived` |
| `deprecated` | description or topics say deprecated, unmaintained, no longer maintained, superseded, or moved to |
| `dormant` | not archived, and `pushedAt` older than `--dormant-years` (default 2) |
| `old-star` | informational only: starred more than `--old-star-years` (default 4) ago and in no list; never proposed for unstarring on its own |

A repository with no reason is not reported. The scan never proposes unstarring a repository the user owns.

## Workflow

1. `sh scripts/run.sh doctor` (shared bootstrap).
2. `sh scripts/run.sh scan --out prune.json` writes every flagged repository with its reasons, `pushedAt`, `starredAt`, lists, and a proposed `action` of `unstar` for `disabled`, `archived`, `deprecated`, and `keep` for `dormant`.
3. The agent groups the candidates by reason, shows them, and the user adjusts actions. Moving a repository to an Archive list instead of unstarring it is handed to `star-lists`.
4. `sh scripts/run.sh apply prune.json --yes` writes a backup (each unstarred repository's id, name, and list memberships), unstars, and re-reads the stars to verify none of them remain.
5. `sh scripts/run.sh restore <backup> --yes` re-stars and puts each repository back into its lists.

## Limits stated to the user

- Re-starring cannot restore the original `starredAt`; a restored star sorts as new.
- GitHub redirects renamed repositories transparently, so a rename is not a signal; only a description that says "moved to" is.
- `dormant` is a fact about the repository, not a judgement on its value. Finished libraries are often dormant and fine, which is why the default action for it is `keep`.

## Language

Everything generated (the candidates file, backups, reports) is English. The English-only test from `star-lists` covers this skill too.

## Test plan

- Unit tests for classification (each reason, owned repositories skipped, thresholds), apply ordering and backup content, restore, and the CLI exit codes, with an in-memory account.
- The shared `bootstrap.sh` keeps the existing `run.sh` tests, re-pointed at the shared copy.
- A read-only scan against a real account, then a single real unstar of a disposable star followed by restore.
