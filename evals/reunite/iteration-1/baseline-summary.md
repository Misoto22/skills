# Reunite — iteration 1 rollout

## What this iteration is

The first scored run of the suite after reunite was rewritten in #116 to align every account byte for byte, carry archives and deletions, and gain `--from`. The rewrite dropped one sentence the tuning cases rely on — why a plain union cannot repair a rename — and the refusal to prune never mentioned `--undo`.

## Rollout

`run-evals-experiment.py`, with-skill arm, 2 samples per case, `deepseek-default` as candidate and judge, reasoning effort `none`, HEAD `510f151` clean. Run one case at a time: the gateway's 404 bursts void a sample and the runner then marks every later case `not_run`, so a whole-suite pass returned five of six cases at best.

Routing (`run-evals.py`, all 9 cases): 9/9.

| Case | Split | Before |
| --- | --- | --- |
| nothing-was-deleted | tuning | 2/2 |
| refuses-to-prune | tuning | 1/2 — did not offer `--undo` |
| restart-is-part-of-the-result | tuning | 2/2 |
| titles-reach-the-other-accounts | tuning | 0/2 — no "entry already present"; judge also wanted "reunite" named rather than `scripts/merge.py` |
| desktop-login-is-not-the-cli-login | tuning | 2/2 |
| synthetic-sandbox-merge | tuning | 1/2 in a separate earlier run; void in every gated run |
| report-before-writing | holdout | 1/2 |

## What passed that the edit could break

`restart-is-part-of-the-result` and `nothing-was-deleted` sit next to the two paragraphs edited; both were re-scored.
