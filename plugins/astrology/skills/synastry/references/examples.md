# Calculator examples

Use these synthetic cases to apply the workflow. Do not reuse their identities, places, dates, or context as defaults.

## Contents

1. Exact records and automatic hand-off
2. Date-only uncertainty
3. Ambiguous daylight-saving refusal
4. Strict Swiss backend refusal

## 1. Exact records and automatic hand-off

**Request:** Two user-supplied records identify country-qualified birthplaces in Coimbra, Portugal, and Busan, South Korea. Both times are documented to within five minutes.

**Action:** Resolve each place and IANA timezone from current sources, state the selected results, and encode both births with `time_mode: "exact"` and their declared `time_accuracy_minutes`. Keep the request's identity and relationship fields limited to what the user supplied.

Run:

```bash
python3 scripts/compute_synastry.py --request request.json --out artifacts
```

On success, retain the one `.json` path printed by the CLI and invoke `$synastry-reading` with that exact path. Do not create a human-readable calculation companion.

## 2. Date-only uncertainty

**Request:** One subject has an exact record for Nairobi, Kenya. The other knows only a civil birth date and the country-qualified birthplace used to resolve `Pacific/Auckland`.

**Action:** Encode the second birth as:

```json
{
  "date": "1995-04-18",
  "time_mode": "date-only",
  "timezone": "Pacific/Auckland"
}
```

Do not add a time or coordinates. Expect sampled position ranges, `confirmed` or `possible` aspects with orb ranges, and no houses or overlays. A valid date-only artifact is uncertain, not incomplete.

## 3. Ambiguous daylight-saving refusal

**Request:** An `exact` record says `2024-11-03 01:30` in `America/New_York` but provides neither `timezone_fold` nor an offset record.

**Action:** Stop before calculation. Explain that the wall time occurs twice. Ask for `timezone_fold: 0` or `timezone_fold: 1`, or a documented `utc_offset_hours` with `utc_offset_reason`. Do not select one occurrence from context or convenience.

Use the same fail-closed rule for a `window` whose endpoint is ambiguous. A window cannot carry `timezone_fold`; require a reasoned offset for the interval or different unambiguous bounds.

## 4. Strict Swiss backend refusal

**Request:** `ephemeris_policy` is `swiss-only`, but the configured data path makes the binding return Moshier flags.

**Result:** The run fails and writes no artifact.

**Reply:** State that Swiss Ephemeris data was unavailable. Ask for a correct `--ephemeris-path`, or ask the user to explicitly choose `allow-moshier` after accepting its recorded limitation. Never relabel fallback positions as Swiss output.
