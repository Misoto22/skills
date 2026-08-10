# Published skills

Only release-ready, recursively discoverable skills belong in this directory.

- [synastry](synastry/SKILL.md) — validates two supplied birth records and produces one uncertainty-aware JSON v2 artifact with backend provenance; it calculates houses only for exact records and overlays only when both records are exact, then hands the artifact to the reading skill.
- [synastry-reading](synastry-reading/SKILL.md) — privately validates an existing JSON v2 artifact and writes an adaptive, evidence-linked report whose relationship modules come only from explicit user context.

`shared/` contains the v2 synastry schema and integrity implementation plus the
astrology license vendored into both skills. Calculation and interpretation use
the same closed artifact contract without relying on files outside a skill
directory at runtime.
