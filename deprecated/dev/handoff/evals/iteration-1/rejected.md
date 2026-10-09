# Rejected edits

No instruction edits were rejected. The three bounded corrections passed the clean comparison gate.

## Superseded baseline

The initial baseline retained an obsolete hook expectation that equated one missing hook with one-way synchronization. The watcher now reconciles both stores independently. That baseline is retained locally but cannot gate this revision. The corrected tuning suite is frozen before measuring a replacement baseline; the holdout cases are unchanged.

## Prompt and expectation mismatch

The first fixed-commit comparison asked only about Claude sidebar visibility but required an explanation of Codex registration. Two correct focused candidate replies were therefore rejected. The diagnostic prompt also expected an explanation of hook feedback without explicitly asking why. The tuning prompts now ask those questions directly; their expectations are unchanged. The previous records remain historical calibration evidence and are excluded from release gating. A new clean baseline and candidate measurement use the same corrected prompts. No held-out prompt or expectation changed.

## Incomparable measurement records

Earlier runs included iteration documentation in the suite fingerprint. Those
records remain immutable and cannot establish a comparison. The corrected
fingerprint covers declared evaluation inputs only. Fresh baseline and first
candidate runs use matching evaluation code, clean commits, the same suite,
and the same model configuration. The accepted gate improved tuning from 2/9
to 6/9 with holdout unchanged at 3/3.
