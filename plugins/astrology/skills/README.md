# Published skills

Only release-ready, recursively discoverable skills belong in this directory.

- [synastry](synastry/SKILL.md) — computes two natal charts, the aspects between them, and both directions of house overlay as a raw data file, then hands it to the reading skill.
- [synastry-reading](synastry-reading/SKILL.md) — interprets a completed synastry data file through fixed relationship mechanisms and evidence-selected real-life domains.

`shared/` contains the v2 synastry schema and integrity implementation plus the
astrology license vendored into both skills. Calculation and interpretation use
the same closed artifact contract without relying on files outside a skill
directory at runtime.
