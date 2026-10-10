# Published skills

Only release-ready, recursively discoverable skills belong in this directory.

- [star-lists](star-lists/SKILL.md) — sorts starred repositories into GitHub star Lists through a checked, diffed, backed-up plan file.
- [star-prune](star-prune/SKILL.md) — flags archived, deprecated and dormant stars and unstars the confirmed ones, with a backup that restores them.

`../shared/` holds what both skills run: `bootstrap.sh` (dependency, sign-in and scope
checks, and the checksum-verified install of gh and uv) and `github_api.py` (the
GraphQL client). Edit it there; `scripts/sync-shared.py` vendors it into each skill.
