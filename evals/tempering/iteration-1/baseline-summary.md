# Tempering — iteration 1 rollout

First scored run of the suite. `run-evals-experiment.py`, with-skill arm, 2 samples per case, `deepseek-default` candidate and judge, one case per run, HEAD `0420dcc`. Routing (`run-evals.py`): 9/9.

| Case | Split | Before |
| --- | --- | --- |
| three-registers-keep-the-date | tuning | 1/2 — one sample closed with "Register 3 works because…", a recommendation by annotation |
| compliance-is-not-softened | tuning | 2/2 |
| third-follow-up-goes-to-record | tuning | 2/2 |
| reverse-mode-without-subtext | tuning | 0/2 — multi-section reading, a rewrite and action advice for a plainly polite line |
| already-appropriate | holdout | 1/2 |

What could break: the two escalation cases sit beside the "do not recommend" rule the second edit widens; both were re-scored.
