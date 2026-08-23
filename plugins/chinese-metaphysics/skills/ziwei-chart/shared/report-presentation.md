# Reading report presentation contract

Apply this contract after the reading skill validates and indexes its source artifact.

## Two-output boundary

Write a reader report and a separate evidence artifact. They serve different readers and must not be merged.

- The reader report is the default handoff. Write it in the user's language as a detailed, human-first interpretation. It may include a compact **Model data card** with rounded values the user asked to see.
- The evidence artifact is the audit handoff. It holds source validation, exact source values, raw ids, checksums, model ids, arithmetic, ledgers, and sensitivity variants.
- Link to the evidence artifact once as the final line of the reader report. Do not expose its machine detail before that link.

## Reader report

- Start with the relationship or natal pattern in plain language, then explain why it matters to the reader. Do not begin with a model disclaimer, source confidence, or calculation method.
- Write only the user's language in headings, labels, prose, and data-card explanations. Translate template headings semantically.
- Do not use numbered evidence markers, raw evidence ids, checksums, model ids, ledger keys, exact arithmetic, stored `left`/`right` labels, or unrounded values.
- Use conditional language for metaphysical interpretation. State the heuristic limitation once, near the compact data card or closing note; do not repeat it in every paragraph.
- Keep only decision-relevant findings. Do not restate a dimension in a score table, a finding list, and a prompt.
- Show reader-facing scores and percentages as whole numbers. Label them as model references, not probabilities, diagnoses, or verdicts.
- Make prompts observable and reversible. Do not give medical, legal, financial, employment, or relationship commands.

## Minimum narrative depth

Unless the user explicitly asks for a brief reading, write a full interpretation rather than an executive summary.

- Target 1,400–1,900 Chinese characters for a natal reader report and 1,800–2,400 Chinese characters for a compatibility reader report; use comparable depth in other languages.
- Give every major conclusion its everyday expression, a countervailing condition or tension, and a practical way to observe it. Do not pad with generic reassurance or repeat the same score in prose.
- Develop the central pattern, main tension, and each person's experience in two or three paragraphs where the source evidence supports that depth. Keep the data card compact and technical evidence separate.

## Model data card

Use a small data card late in the reader report. It must make numbers legible without making them the story.

- Show the displayed primary score and no more than three supporting indicators in a compatibility reader report. If a relationship context was selected, display that contextual score before the general reference.
- Show the five-element distribution and day-master reference in a natal reader report, with a one-sentence heuristic limitation.
- Keep the complete dimension table, exact weights, and all exact values in the separate evidence artifact.

## Optional ink-wash poster

A poster is a third artifact, never a substitute. Write the reader report and the evidence artifact first; offer the poster only when the user asks for a visual, shareable, or printable report, and never from a source that failed validation.

- Follow `shared/divination-report/poster-contract.md` for the payload shape and the renderer command.
- The model writes data only. Never write the HTML by hand and never edit the template for one reading — the division is what keeps the limitation footer and the disclosure table from being edited away.
- Every rule above still applies to the poster: whole numbers, model-reference labels, no raw ids or checksums, and a recorded disagreement stays recorded.
- `footer.evidence_link` is the only bridge from the poster to machine detail.

## Evidence artifact

Use the same user language for prose labels, but preserve raw ids and machine values exactly.

- Begin with source status and the checksum or explicit `pasted-complete` limitation.
- Mirror the reader report's headings in a claim map. Under each heading, list the exact source facts and ledger records that support or limit its prose; this replaces inline reader citations.
- Include every raw id required by the reading skill, exact values, source and comparison checksums, model versions, arithmetic, stored ownership, and sensitivity variants.
- Treat conflicting evidence as a recorded tension. Do not hide a negative ledger or select the favorable alternate.
