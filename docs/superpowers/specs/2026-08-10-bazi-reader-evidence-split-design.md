# BaZi reader and evidence split design

## Goal

Make the default natal and compatibility reports readable as guidance for a person while preserving every calculation, identifier, checksum, and ledger in a separately addressable audit artifact.

## Output boundary

Each reading skill writes two UTF-8 Markdown files after validating its existing JSON source:

1. A reader report at the existing `bazi_reading_*.md` or `bazi_compatibility_reading_*.md` path.
2. A sibling `bazi_reading_evidence_*.md` or `bazi_compatibility_evidence_*.md` file.

The reader report has no numbered evidence markers, raw identifiers, checksums, model IDs, weighted arithmetic, or unrounded values. It contains a compact model data card: rounded values that the user asked to see, labeled as model references rather than probabilities or verdicts. Its final line links once to the evidence artifact.

The evidence artifact contains source validation status, exact source values, raw IDs, ownership, weights, arithmetic, sensitivity variants, checksums, and a heading-based mapping back to each reader-report claim. It is an audit document, not part of the normal reading flow.

## Reader report shape

Natal reports use five human questions: the main pattern; chart tendencies; strengths and tensions; relationship, work, and reflection; and model data card.

Compatibility reports use six human questions: the relationship pattern; what draws the pair together; the main friction; each person’s likely experience; low-risk observations and questions; and model data card. The selected relationship-context score is displayed in the data card ahead of the general reference. Direction remains `Name A → Name B`.

The report uses plain language, conditional framing, and concrete observations. It does not repeat a score as a conclusion, force seven dimensions into the reader’s attention, or treat the model as a decision-maker.

## Non-goals and safeguards

Do not change chart calculation, scoring, schemas, validation, source checksums, sensitivity handling, or the ban on deterministic predictions and high-stakes instructions. Do not infer a relationship stage from names or demographics; use supplied context only when present.

## Verification

Add contract and evaluation coverage for separate evidence artifacts, no reader citations, compact data cards, directional naming, selected-context priority, and all audit details retained in the evidence file. Regenerate the Henry and Cindy natal and compatibility samples, inspect reader/evidence separation, then run synchronization, eval, repository, lint, format, shell, and unit checks.
