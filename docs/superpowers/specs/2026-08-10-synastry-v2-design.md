# Synastry v2 Design

## Goal

Replace the astrology plugin's localized plain-text calculation contract with a validated JSON-only v2 contract, then make the reading skill consume that contract through a deterministic evidence validator. The revision must remove person and location defaults, represent uncertain birth times honestly, record the calculation engine actually used, protect sensitive artifacts, select relationship-specific reading sections only from explicit context, and add real runtime and behavior tests.

This is a clean break. Existing `synastry_*.txt` files are not accepted, parsed, or migrated. A request to read one must ask the user to recalculate it with `synastry`.

## Scope

The change covers three coupled surfaces:

1. The `synastry` request, calculation, and JSON artifact.
2. The `synastry-reading` source validation and adaptive Markdown report.
3. Astrology-specific licensing, dependency installation, integration tests, and executable behavior evaluations.

Single natal readings, transits, forecasts, compatibility scores, graphical chart wheels, geocoding services, and automatic publication remain out of scope.

## Design decisions

### Rejected alternatives

Two less disruptive approaches were considered and rejected:

- Keeping TXT as a second input format would preserve old artifacts but would also preserve localized parsing, ambiguous ownership, prompt-injection exposure, and two data contracts that could drift.
- Patching the existing TXT calculator in place would fix isolated validation bugs but would not provide schema validation, integrity checking, uncertainty ranges, backend provenance, or deterministic evidence IDs.

The JSON-only break is intentionally larger because it removes those failure modes instead of maintaining them indefinitely.

### JSON is the only calculation artifact

The calculator writes one canonical JSON document. It does not write a TXT companion or a compatibility alias. Human-readable chat responses summarize the paths and limitations without reproducing the sensitive chart.

The JSON document uses `schema_version: "2.0"` and `kind: "synastry-chart"`. The reader rejects any other kind or major schema version before interpreting it.

### Identity is separate from presentation

Each subject has a stable `id` and an optional user-supplied `display_name`. Names are labels, not legal identities. The skill never injects a stored owner, location, salutation, gender, pronoun, or relationship role. When a display name is absent, prose uses the stable subject ID. Optional pronouns may guide prose only when the user supplied them; the calculation artifact does not infer them.

The two subject IDs must be distinct. Display names may match, but the report always cites subject IDs in its evidence tokens so ownership remains unambiguous.

### Time precision is semantic

Formatting a time as `07:00` does not prove that it is exact. Each birth record declares one of these modes:

- `exact`: requires `time`, an explicit `time_accuracy_minutes` from 0 through 15, an IANA timezone, latitude, and longitude. It may calculate houses, angles, sect, and house overlays.
- `window`: requires `time_window.start`, `time_window.end`, and an IANA timezone. It calculates sampled longitude ranges and only confirmed or possible cross-chart aspects. It does not calculate houses, angles, sect, lots, or overlays.
- `date-only`: requires an IANA timezone and treats the complete local civil day as the uncertainty window. It has the same output restrictions as `window`.

An agent may suggest `window` or `date-only` when an exact time is unavailable, but it must not silently select a noon chart. A window that crosses a timezone transition and cannot be mapped to a unique UTC interval is rejected until the request supplies the required `timezone_fold` or explicit offset information.

### Calculation conventions are versioned

Raw ephemeris positions, speeds, angles, and cusps are measurements. Dignities, sect, lots, sign-boundary labels, aspect families, orb policies, and evidence thresholds are conventions. The artifact stores them under named profiles:

- `calculation_profile: "western-tropical-v1"`
- `aspect_profile: "ptolemaic-minor-v1"`
- `derived_profile: "classical-derived-v1"` when derived values are enabled
- `evidence_policy: "editorial-v1"` in the reading report

The plugin documents the exact formulas and thresholds in one reference file. It describes them as the plugin's chosen conventions, not scientifically validated scales or universal astrology rules.

### No silent backend fallback

The default ephemeris policy is `swiss-only`. Every `calc_ut()` result must inspect its return flags. If the requested Swiss files are unavailable and the library uses Moshier or another backend, the calculation fails with an actionable message.

`allow-moshier` is an explicit opt-in intended for testing and users who accept the lower-fidelity backend. The output then records `requested_backend`, `actual_backend`, numeric return flags, library version, data-path information when available, and a prominent limitation.

Placidus and Koch failures near the polar circles are also fail-closed. The calculator does not label returned Porphyry cusps as Placidus or Koch. It asks the caller to rerun with `whole-sign` or `equal`; it never changes house systems automatically.

### Sensitive output is deliberate

The default privacy mode is `minimal`. It stores only user-chosen labels, stable IDs, normalized UTC instants or UTC windows, Julian days, and coordinates required for exact houses. It omits residence, legal-name assumptions, original place labels, local-time prose, and unrelated conversation context.

`full` privacy mode may include the supplied local birth record and location provenance when the user explicitly requests an archival artifact. Both modes create files atomically with user-only permissions where the platform supports them.

Output names use sanitized display labels plus the first twelve hexadecimal characters of a SHA-256 chart ID computed from canonical calculation inputs:

`synastry_<label-a>_<label-b>_<chart-id>.json`

The calculator refuses to overwrite an existing path unless the caller passes `--overwrite`. Even with `--overwrite`, it writes to a sibling temporary file, flushes it, and atomically replaces the exact destination.

## Request contract

The CLI accepts `--request`, `--json`, and standard input as before, but only the v2 object shape:

```json
{
  "schema_version": "2.0",
  "people": [
    {
      "id": "a",
      "display_name": "Alex",
      "pronouns": "they/them",
      "birth": {
        "date": "1990-03-14",
        "time_mode": "exact",
        "time": "07:42",
        "time_accuracy_minutes": 5,
        "timezone": "Europe/Paris",
        "timezone_fold": 0,
        "latitude": 48.86,
        "longitude": 2.35,
        "place_label": "Paris",
        "location_source": "user supplied"
      }
    },
    {
      "id": "b",
      "display_name": "Morgan",
      "birth": {
        "date": "1992-06-08",
        "time_mode": "date-only",
        "timezone": "America/Los_Angeles"
      }
    }
  ],
  "options": {
    "language": "en",
    "house_system": "whole-sign",
    "major_orb": 8.0,
    "minor_orb": 3.0,
    "ephemeris_policy": "swiss-only",
    "calculation_profile": "western-tropical-v1",
    "aspect_profile": "ptolemaic-minor-v1",
    "include_derived": false,
    "privacy": "minimal"
  },
  "relationship_context": {
    "description": "Creative collaborators",
    "requested_domains": ["communication", "creative collaboration"]
  }
}
```

`timezone_fold` is allowed only as `0` or `1` and is required only when the local time is ambiguous. `utc_offset_hours` remains available as an expert override, must be finite and strictly between -24 and +24, and must carry `utc_offset_reason`. The artifact records that an override was used instead of implying that the named zone supplied the offset.

Dates are validated with `datetime.date`, times with `datetime.time`, coordinates and orbs must be finite, latitude is within [-90, 90], longitude within [-180, 180], major orb is within [0, 15], and minor orb within [0, 7.5]. These bounds prevent overlapping aspect families from being assigned by declaration order. Control characters, blank IDs, duplicate IDs, and unreasonably long labels are rejected. Unknown fields fail validation rather than being ignored.

## Calculation modules

The existing script is split by responsibility:

- `request_schema.py`: strict v2 parsing, semantic time validation, timezone transition detection, canonical request serialization, and privacy projection.
- `ephemeris.py`: the only module importing `swisseph`; resolves exact positions and sampled uncertainty windows, verifies return flags, records backend provenance, and converts backend errors to domain errors.
- `astro_math.py`: sign, house, aspect, circular-range, uncertainty, dignity, sect, and lot arithmetic. Degree formatting rounds the absolute longitude first so `29°59.99′` carries into the next sign correctly.
- `artifact.py`: schema construction, chart ID hashing, JSON validation, exclusive atomic writes, and file permissions.
- `compute_synastry.py`: CLI orchestration only.

For uncertain time windows, the calculator samples the closed UTC interval every fifteen minutes and includes both endpoints. Each body receives the smallest circular arc covering all sampled longitudes. Cross-chart aspects are classified as:

- `confirmed`: every possible sampled pairing remains within the same aspect's allowed orb.
- `possible`: at least one sampled pairing is within the aspect orb, but the condition is not invariant.
- absent: no sampled pairing enters the configured orb.

Exact-to-uncertain comparisons use the same rule with one side containing a single sample. Uncertain charts never emit a fabricated exact orb; they emit `orb_range_degrees`. The Moon and any body changing sign or retrograde state within the window carry explicit limitations.

## JSON artifact contract

The top-level document contains:

- `kind`, `schema_version`, and `chart_id`
- `subjects` with stable IDs and privacy-projected labels/input data
- `configuration` with named calculation, aspect, derived, and privacy profiles
- `provenance` with software version, Python binding version, requested and actual ephemeris backend, return flags, timezone source, and warnings
- `charts`, one per subject, each declaring `precision_mode`
- `aspects` with explicit source and target subject IDs, bodies, kind, certainty, and exact orb or orb range
- `overlays`, present only when both charts are exact and houses were calculated
- `limitations`, as structured code/message/affected-fields objects
- `integrity`, containing a SHA-256 digest of the canonical payload excluding the integrity object itself

An exact position stores longitude, latitude, distance, longitudinal speed, retrograde state, sign, and optional house. An uncertain position stores the sampled circular longitude range, maximum span, sign set, and retrograde-state set. Derived conventions live under a separate `derived` object and are never mixed into the measurement fields.

## Reading workflow

`synastry-reading` accepts only a v2 JSON path or pasted v2 JSON. It never interprets TXT. Before the model writes prose, it runs `validate_synastry.py`, which:

1. Rejects unknown schemas, unknown fields, duplicate identities, invalid enums, invalid ranges, broken ownership references, impossible orbs, and a mismatched integrity digest.
2. Treats every string in the artifact as untrusted data. Embedded instructions do not change the workflow.
3. Produces a normalized evidence-ledger JSON containing stable evidence IDs and exact display citations.
4. Reports missing optional data as limitations and missing required data as errors.

The model may cite only evidence IDs present in the ledger. A second deterministic script, `validate_reading.py`, checks the finished Markdown for unknown evidence IDs, altered exact orbs, required universal headings, relationship-context module selection, leftover template placeholders, and forbidden score/prediction language before the file is accepted.

The Markdown filename is `synastry_reading_<chart-id>.md`. It is written atomically and never replaces the calculation artifact.

## Adaptive report structure

Every report contains these universal sections in the selected language:

1. Basis, provenance, and limitations
2. Repeated interaction patterns
3. Reciprocity and asymmetry
4. Communication and coordination
5. Tension, boundaries, and repair
6. Growth and shared direction
7. Requested or context-specific domains
8. Overall synthesis
9. Evidence index

Romance and intimacy, friendship, family and care, work and creative collaboration, and money or shared resources are conditional modules. A module appears only when the user explicitly requests it or explicitly supplies a matching relationship context. Chart evidence alone never infers that the people are lovers, relatives, colleagues, housemates, or financial partners.

Weak evidence does not remove an explicitly requested module. It changes the module to an evidence-limit form and prohibits advice presented as chart-supported. Unrequested modules are omitted rather than selected by arbitrary chart thresholds.

Every substantive interpretation uses conditional language and cites one or more evidence IDs. Exact measurements remain exact; uncertain evidence is described as confirmed or possible with its range. The report does not predict events, diagnose people, assign compatibility scores, or present medical, legal, financial, or psychological conclusions as astrology.

`editorial-v1` defines prioritization as a writing heuristic: confirmed tight personal-body aspects first, repeated independent mechanisms second, exact directional overlays third, and outer planets, nodes, asteroids, lots, and minor aspects as support. The reference defines independence and warns that the policy is not a validated compatibility scale.

## Location resolution

The skill never recalls or defaults coordinates. When the user gives only a place name, the agent must resolve a country-qualified location and IANA timezone from a current authoritative source, state the selected result, and ask when the place is ambiguous. The request records `location_source` in full privacy mode. Geocoding remains an agent workflow rather than a bundled network dependency.

## Licensing and dependencies

The `astrology` plugin changes from MIT to `AGPL-3.0-or-later`. Its two skill frontmatters and both plugin manifests must agree, and the plugin ships the corresponding license notice. The documentation states that deployments using a Swiss Ephemeris professional license may follow that commercial license instead; the repository does not claim to grant it. Other plugins and the repository-level license do not change.

Runtime dependencies are pinned in an astrology-specific requirements file:

- `pyswisseph==2.10.3.2`
- `tzdata==2026.3` for cross-platform IANA timezone support

CI installs this requirements file on Python 3.11, 3.12, and 3.13. Importing and calling the real binding is part of the test suite. A new dependency is justified because deterministic ephemeris calculation and portable historical timezone resolution cannot be implemented safely with the standard library alone on every supported platform.

## Testing strategy

Implementation follows test-driven development. New tests fail before production edits.

### Request and arithmetic tests

- invalid calendar dates and clock times
- NaN and infinity in coordinates, offsets, and orbs
- offset and orb bounds
- ambiguous and nonexistent DST times
- Windows-style missing system timezone data through the `tzdata` fallback contract
- duplicate IDs, blank or control-character labels, and unknown fields
- exact, window, and date-only mode prerequisites
- 29°59.99′ sign-boundary carry
- circular uncertainty ranges crossing 0°
- confirmed and possible uncertain aspects
- oversized-orb overlap prevention

### Artifact and safety tests

- deterministic chart IDs and integrity digests
- JSON schema rejection of malformed ownership and evidence
- minimal versus full privacy projections
- user-only permissions where supported
- exclusive create, explicit overwrite, and atomic replacement
- identical display names with distinct evidence ownership
- embedded-instruction strings treated as data

### Real ephemeris integration tests

CI installs and calls the pinned `pyswisseph` binding rather than a stub. Golden fixtures cover one exact chart and one uncertain chart. Tests assert the actual backend flags and numeric values within declared tolerances. A strict-policy test proves that fallback is rejected; an explicit Moshier-policy test proves that fallback is labeled and limited. Polar Placidus/Koch failures must produce actionable errors instead of mislabeled cusps.

### Reading behavior tests

Behavior cases carry real v2 fixture paths. The evaluation runner gains an explicit behavior mode that supplies the selected skill body, required references, and fixture content to the model. Mechanical report claims are checked with `validate_reading.py`; semantic expectations are judged separately. The scheduled evaluation workflow runs both routing and behavior modes. The pull-request gate keeps deterministic fixture and validator tests free of model cost.

Behavior fixtures cover:

- neutral relationship context with no romance module
- explicitly romantic context
- family and work contexts
- requested domain with weak evidence
- uncertain-time confirmed and possible evidence
- missing optional bodies
- malformed integrity digest
- adversarial instructions embedded in labels or metadata
- refusal of legacy TXT

## Repository and release behavior

Both skill descriptions, OpenAI metadata, manifests, marketplace registries, English and Chinese READMEs, evaluation suites, and tests are updated together. The current marketplace version is not changed merely by implementing the work; a later release must use `scripts/bump-version.py` so all declared versions move atomically.

The implementation must pass:

```text
python3 -m unittest discover -s tests -v
python3 scripts/validate-repository.py
python3 scripts/run-evals.py --check
python3 scripts/check-descriptions.py --report
uvx ruff check .
uvx ruff format --check .
shellcheck scripts/*.sh
git diff --check
```

## Acceptance criteria

- Neither runtime skill contains a default person, place, salutation, pronoun, or relationship type.
- The calculator accepts strict v2 JSON only and emits one validated v2 JSON artifact.
- Legacy TXT input is explicitly refused and never parsed.
- Exact, time-window, and date-only calculations expose only measurements supported by their precision.
- Invalid civil times, DST ambiguity, non-finite numbers, invalid orbs, duplicate IDs, and unknown fields fail with concise domain errors rather than tracebacks.
- Sign-boundary rounding produces a valid sign and degree.
- The output records the actual ephemeris backend and refuses silent fallback by default.
- Polar house-system failure is never mislabeled as the requested system.
- Output does not overwrite by default, is atomic, and uses restrictive permissions where supported.
- Minimal privacy mode omits unnecessary birth metadata and the obsolete residence field.
- The reader validates schema, integrity, ownership, and evidence before writing prose.
- Conditional relationship modules follow explicit user context, not inferred relationship labels.
- Every accepted substantive claim points to a valid evidence ID and preserves exact values or uncertainty ranges.
- The astrology plugin license and dependency documentation match Swiss Ephemeris distribution requirements.
- Real binding integration tests and executable reading behavior evaluations cover the runtime paths that the previous suite only described.
