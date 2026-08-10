# Reading report presentation contract

Apply this contract after completing the reading skill's report-specific source validation and evidence indexing.

## Localization

- Write the entire report in the user's language, including every heading, table label, disclaimer, and final technical appendix label.
- Treat headings and labels shown in a template as semantic examples. Translate them; do not select from a fixed language pair or render bilingual labels unless the user's requested language requires them.
- Preserve raw evidence ids, checksums, model ids, and other machine values exactly when they appear in the technical appendix; localization applies to the prose and labels around them.

## Reader-layer citations

- Use compact sequential markers `〔1〕`, `〔2〕`, and so on in the reader layer. Cite every substantive sentence that makes a source, calculation, or interpretive claim with one or more markers.
- Show only compact markers in reader prose. Do not expose raw evidence ids there.
- In the final technical appendix, map every used marker to one exact raw evidence id, its exact source value, and its evidence class. Include stored ownership or direction when the report-specific contract requires it.
- Keep the mapping deduplicated and complete: one raw id maps to one source fact, every reader marker has a mapping, and every mapped marker is used in the reader layer.
- When evidence conflicts, describe the tension instead of choosing the more favorable result.

## Display precision

- Display scores and percentages as whole numbers in the reader layer. Keep the exact unrounded values in the final technical appendix.
- Display sensitivity minimum, maximum, and spread as whole numbers in the reader layer; keep exact variant scores and spreads in the appendix. An exact boundary fact, such as a changeover time, may appear in plain reader language when it is necessary to explain a material boundary effect, but its raw id remains appendix-only.

## Technical appendix boundary

- Put the technical appendix last and keep the earlier, report-specific sections as the reader layer.
- Keep full checksums, model ids, exact arithmetic, unrounded values, and raw evidence ids in the final technical appendix only.
- Include the report-specific validation status, calculation details, and evidence fields required by the reading skill without moving those technical records into reader prose.

## Worked boundary

Translate the prose in this example into the user's language; preserve only the raw id and machine value verbatim.

- Before, in reader prose: `The heuristic score [score.raw] is 59.99.`
- After, in reader prose: `The heuristic score is 60.〔1〕`
- In the final appendix: `` `〔1〕` | `[score.raw]` | `59.99` | calculated heuristic ``
