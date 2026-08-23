# Ink-wash poster contract

A poster is an optional third artifact, never a replacement. A reading skill still
writes its reader report and its separate evidence artifact; the poster is a
single self-contained HTML page for the reader who wants one screen to keep.

Offer it only when the user asks for a visual, shareable, or printable report.
Never produce one from a source that failed validation.

## The division that makes this safe

The model writes **data only**. Every colour, column, and rule lives in
`templates/ink-wash-poster.html`, so a model can neither restyle the page nor
delete the limitation footer.

```
verified source artifact  ──▶  poster payload JSON  ──▶  render_poster.py  ──▶  one .html
        (calculator)              (reading skill)          (this component)
```

Never write HTML directly, never edit the template per reading, and never inline
a value the source artifact does not carry.

## Run it

```bash
python3 shared/divination-report/render_poster.py --data POSTER_PAYLOAD.json --out NAME_poster.html
```

The command prints one absolute path on success. Exit code 2 means the payload
failed validation or the template still held an unresolved tag; report that
error rather than hand-writing the page. Only pass `--template` when a skill
ships a variant template of its own.

## Payload

Write it in the user's language. `meta.seal` takes one or two characters, since
it renders inside a vertical seal box.

```jsonc
{
  "meta": {
    "seal": "命盤",              // 1-2 characters
    "archetype": "...",          // 3-9 characters; the poster's title
    "one_line": "...",           // <= 30 characters
    "subject": "...",            // display name from the source artifact
    "system_label": "..."        // e.g. 八字 · 紫微綜合印證
  },
  "identity":     [{ "label": "...", "value": "..." }],            // <= 8
  "core_metrics": [{ "label": "...", "value": "...",
                     "note": "...", "ratio": 0 }],                 // <= 6; ratio 0-100, optional
  "axes":         [{ "system": "...", "statement": "..." }],       // <= 4
  "consistency":  { "verdict": "...", "verdict_class": "...", "note": "..." },
  "distribution": { "title": "...", "items": [{ "label": "...", "value": "...", "ratio": 0 }] },
  "tendencies":   { "strengths": [{ "title": "...", "detail": "..." }],
                    "tensions":  [{ "title": "...", "detail": "..." }] },
  "domains":      { "rows": [{ "name": "...",
                               "readings": [{ "system": "...", "text": "..." }],
                               "verdict": "...", "verdict_class": "...", "fused": "..." }] },
  "conflicts":    { "rows": [{ "point": "...",
                               "positions": [{ "system": "...", "text": "..." }],
                               "impact": "...", "impact_class": "...", "advice": "..." }] },
  "narrative":    { "title": "...", "paragraphs": ["...", "..."] },
  "reflection":   { "items": ["...", "..."] },
  "confidence":   { "items": [{ "label": "...", "level": "...", "ratio": 0 }], "note": "..." },
  "footer":       { "limitation": "...", "evidence_link": "...", "generated_at": "YYYY-MM-DD" }
}
```

`meta`, `identity`, `core_metrics`, `axes`, `narrative`, and `footer` are
required. Every other block is optional and its section disappears when omitted;
omit a block rather than filling it with placeholder text.

### Fixed class values

Pass the class alongside the label so the template can colour it. Any other
value renders unstyled.

| Field | Allowed |
| --- | --- |
| `consistency.verdict_class`, `domains.rows[].verdict_class` | `verdict-aligned`, `verdict-partial`, `verdict-conflict` |
| `conflicts.rows[].impact_class` | `impact-low`, `impact-mid`, `impact-high` |

## What the poster inherits from the reading contract

A poster changes the shape of a reading, never its discipline. The reading
contract your skill already follows still governs every word on the page. In
particular:

- Show whole numbers. `ratio` drives a bar width and is not shown as a figure.
- Label scores as model references, not probabilities, diagnoses, or verdicts.
- Never place a raw evidence id, checksum, model id, ledger key, or exact
  arithmetic on the poster. `footer.evidence_link` points at the evidence
  artifact; that is the only bridge.
- `footer.limitation` is required and carries the heuristic limitation plus the
  no-decision statement. Do not shorten it away.
- Record a real disagreement in `conflicts` rather than resolving it silently.
  A poster that shows only agreement is a failed poster when the source
  disagreed.
- `distribution.items[].ratio` may be normalized so the largest entry reads 100;
  keep `value` as the true figure the reader should see.

## Cross-plugin note

This component is vendored: several subject plugins ship the same copy so each
one stays installable on its own. The copy inside a skill is generated, never
edited. Change it in the repository source and let the sync script rewrite every
copy.
