# Rejected edits

No instruction edits have been rejected yet.

## Superseded baseline

The initial baseline retained an obsolete hook expectation that equated one missing hook with one-way synchronization. The watcher now reconciles both stores independently. That baseline is retained locally but cannot gate this revision. The corrected tuning suite is frozen before measuring a replacement baseline; the holdout cases are unchanged.

## Prompt and expectation mismatch

The first fixed-commit comparison asked only about Claude sidebar visibility but required an explanation of Codex registration. Two correct focused candidate replies were therefore rejected. The diagnostic prompt also expected an explanation of hook feedback without explicitly asking why. The tuning prompts now ask those questions directly; their expectations are unchanged. The previous records remain historical calibration evidence and are excluded from release gating. A new clean baseline and candidate measurement use the same corrected prompts. No held-out prompt or expectation changed.
