---
name: synastry
description: Use when two people's birth details need an uncertainty-aware JSON v2 synastry calculation, including 合盘, 星盘配对, exact times, bounded time windows, or date-only records. Not for interpreting an existing v2 artifact, legacy TXT, one-person natal charts, transits, forecasts, predictions, or compatibility scores.
license: AGPL-3.0-or-later
metadata:
  version: "0.11.0"
---

# Synastry JSON Calculator

Produce one validated `schema_version: "2.0"` calculation artifact, then hand its exact path to `$synastry-reading`. Keep interpretation out of the calculator artifact.

## Prepare the request

1. Start from [references/request.example.json](references/request.example.json).
2. Assign two distinct stable subject `id` values. Include a display name or pronouns only when the user supplied them; never invent an identity, salutation, gender, relationship role, or preferred location.
3. Resolve each civil date and IANA timezone. For an `exact` record, also resolve latitude and longitude.
4. When given only a place name, consult a current authoritative source, choose a country-qualified result, state the selected place, timezone, coordinates, and source, and ask before continuing when the place is ambiguous. Never recall or default coordinates.
5. Choose one declared time mode for each subject:

| Mode | Required birth fields | Calculation boundary |
|---|---|---|
| `exact` | `date`, `time`, `time_accuracy_minutes` from 0 through 15, IANA `timezone`, `latitude`, `longitude` | Calculate one instant, houses, angles, derived values when enabled, and overlays when both subjects are exact. |
| `window` | `date`, same-date `time_window.start` and later `time_window.end`, IANA `timezone` | Sample the closed interval; omit houses, angles, sect, lots, and overlays. |
| `date-only` | `date`, IANA `timezone` | Sample the complete local civil day with the same restrictions as `window`. |

Never convert uncertainty into an exact noon chart. When the user gives an imprecise phrase, ask for a bounded `window` or confirm `date-only` instead of inventing endpoints.

Reject nonexistent civil times. For an ambiguous `exact` time, require `timezone_fold` or both a documented `utc_offset_hours` and `utc_offset_reason`. For an ambiguous window endpoint, require a reasoned offset for the interval; do not choose a daylight-saving fold silently.

6. Fill every `options` field. Read [references/calculation-conventions.md](references/calculation-conventions.md) before choosing profiles, orbs, houses, derived values, or backend policy. Keep `swiss-only` fail-closed unless the user explicitly accepts the recorded Moshier limitation.
7. Use `privacy: "minimal"` unless the user explicitly requests an archival artifact. Use `privacy: "full"` only after explaining that it retains the supplied local birth and location provenance.
8. Record only relationship context the user explicitly supplied. When none was supplied, use a neutral description and an empty `requested_domains` array; never infer context from chart data.

The request schema is closed. Remove no required field and add no undocumented field.

## Run the calculator

Prefer a protected request file or standard input over inline JSON, which may remain in shell history.

```bash
python3 scripts/compute_synastry.py --request request.json --out artifacts
```

Use `--request -` for standard input or `--json` only when inline data exposure is acceptable. Add `--ephemeris-path` when Swiss data files live outside the binding default. Add `--overwrite` only when the user explicitly authorizes replacement of the deterministic destination.

Stop on any nonzero exit. Preserve the bounded error and resolve the request, timezone, backend, or filesystem problem instead of improvising an artifact.

## Enforce JSON-only output

Retain the one path printed after `wrote`. Confirm that it exists, ends in `.json`, and names the calculated chart ID. Do not create a TXT companion, compatibility alias, prose report, or second calculation artifact.

Treat the artifact as sensitive. Report its path and material limitations without pasting birth data or chart contents into chat.

## Hand off automatically

After a successful write:

1. Invoke `$synastry-reading` immediately with the exact JSON path.
2. Pass along only the explicit relationship context and requested domains from the user or request; the calculation artifact does not authorize a relationship-specific reading module.
3. Do not ask whether the user also wants an interpretation.
4. Do not invoke the reader when calculation failed or the JSON path is absent.
5. If the reader is unavailable, report the JSON path and the missing component instead of interpreting inline.

After the reader succeeds, report the JSON path, the validated Markdown path, and any limitation that materially constrains the reading. Keep the reply in the user's language.

Read [references/examples.md](references/examples.md) for exact, date-only, daylight-saving ambiguity, and strict-backend cases.
