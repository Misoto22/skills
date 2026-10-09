# Repo polish — iteration 1 rollout

First scored run. The skill plus linked references exceed 32k input tokens, so every sample at the README's `--max-input-tokens 32000` voided on `candidate_context_limit`; this suite is scored at 64000. Re-scored after #131 supplied the repository facts two cases withheld. HEAD `86a265d`, with-skill arm, 2 samples, one case per run.

| Case | Split | Before |
| --- | --- | --- |
| chinese-request-english-repository | tuning | 1/2 — judge read "keeps the repository's English" as a failure in one sample |
| conflicting-licence-declarations | tuning | 2/2 |
| forge-write-confirmation | tuning | 1/2 — plan table appeared mid-reply, after prose about passes |
| explicit-multiple-repositories | tuning | 1/2 |
| no-licence-declared-anywhere | holdout | 0/2 — blocks every other pass on the licence question |

Routing: 10/10.
