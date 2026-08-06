# Published skills

Only release-ready, recursively discoverable skills belong in this directory.

- [email](email/SKILL.md) — configurable draft/send email workflow with deterministic HTML, pre-send policy gates, artifact hashing, and readback verification.
- [tempering](tempering/SKILL.md) — rewrites a blunt or frustrated workplace message into three registers, keeping the request, the date, and the consequence intact.

Each skill carries a generated `shared/` copy of the plugin's `plugins/writing/shared/`. Edit the plugin-level directory and run `python3 scripts/sync-shared.py`; never edit a copy.

Put work in progress under a top-level `drafts/` directory and retired skills under `deprecated/`; neither location is published by the plugin manifest.
