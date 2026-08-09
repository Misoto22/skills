# Published skills

Only release-ready, recursively discoverable skills belong in this directory.

- [synastry](synastry/SKILL.md) — computes two natal charts, the aspects between them, and both directions of house overlay as a raw data file, then hands it to the reading skill.
- [synastry-reading](synastry-reading/SKILL.md) — interprets a completed synastry data file across love, friendship, business partnership, and money in a fixed evidence-linked Markdown report.

This plugin has no `shared/` directory: calculation and interpretation have
different runtime instructions, and their interface is the generated data file.
