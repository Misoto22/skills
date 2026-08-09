---
name: bazi-chart
description: Calculate one reusable BaZi chart from a named person's exact birth date, minute, and birthplace, write canonical JSON plus data-only Markdown, then start the natal reading automatically. Use for 八字排盘, 生辰八字, four pillars, or informal single-person birth details. Not for two-person compatibility, existing-chart interpretation, Da Yun, annual luck, or event forecasts.
license: MIT
metadata:
  version: "0.8.1"
---

# BaZi Chart

Turn one complete birth record into `bazi_<name>.json` and `bazi_<name>.md`.

The JSON is the reusable machine interface. The Markdown is a human-readable rendering of the same calculation data. Keep interpretation out of both.

## Boundary

- Require a name, exact birth date, time to the minute, and an unambiguous birthplace.
- Never infer a missing minute, place, calendar, leap-month flag, or gender.
- Resolve coordinates and the historical IANA time zone before calculation.
- Use the shared versioned calendar and scoring rules.

## Hand-off

After both artifacts validate, automatically invoke `bazi-reading` with the exact JSON path. If calculation fails, do not invoke the reading skill.

The detailed runtime procedure, request schema, examples, and failure rules are added with the calculator implementation.
