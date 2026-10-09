# BaZi compatibility — iteration 1 rollout

Scored after #131 made the suite answerable (execution fixtures for the hand-off and alternate-range cases). `run-evals-experiment.py`, with-skill arm, 2 samples, `deepseek-default`, one case per run, HEAD `86a265d`. The execution cases need `--max-tool-calls 8 --max-turns 6`; at 4 tool calls every sample voided on `candidate_tool_call_limit`.

| Case | Split | Before |
| --- | --- | --- |
| missing-minute | tuning | 1/2 — one sample read "早上七点" as an exact 07:00 |
| score-contract | tuning | 0/2 — #123 replaced the weights table with a pointer to the rules file, which a text-only run cannot open, so neither sample could state 25/20/20/20/15 |
| automatic-handoff | tuning | 2/2 (64k input cap) |
| alternate-range | holdout | 1/2 (64k input cap) — one sample omitted a primary/alternate combination |

Routing: 7/7.
