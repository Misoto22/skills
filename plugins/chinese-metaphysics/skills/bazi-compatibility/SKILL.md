---
name: bazi-compatibility
description: Compare two people from reusable BaZi chart JSON files, two complete birth records, or one of each; write auditable interaction data and transparent general or relationship-specific scores before automatic interpretation. Use for 八字合婚, 合八字, two-person compatibility, 配不配, or whether two charts work together. Not for one-person natal work, reading an existing comparison, forecasting, or missing birth minutes.
license: MIT
metadata:
  version: "0.8.1"
---

# BaZi Compatibility

Write `bazi_compatibility_<name-a>_<name-b>.json` and a data-only Markdown rendering.

## Boundary

- Accept two validated chart artifacts, two complete birth records, or one of each.
- Reuse an existing chart without recalculation.
- Keep directional evidence attached to the person who gives or receives it.
- Calculate a relationship-neutral score unless the caller states a relationship type.
- Expose every weight, contribution, deduction, confidence reason, and alternate-chart range.

## Hand-off

After the compatibility artifacts validate, automatically invoke `bazi-compatibility-reading` with the exact JSON path. Never hand off a partial or failed comparison.

The calculator implementation adds the full schema, command, score model, examples, and failure rules.
