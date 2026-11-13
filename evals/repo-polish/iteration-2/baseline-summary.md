# Repo polish — iteration 2 rollout

HEAD `aa67ac1` (adds `render-check-unpushed` and `picture-without-asset`), with-skill arm, 2 samples, one case per run, deepseek-default for candidate and judge, `--max-input-tokens 64000`.

| Case | Split | Before |
| --- | --- | --- |
| render-check-unpushed | tuning | 0/2 — one sample never mentions the rendered-page check; the other was failed on a reason that argues for a pass |
| picture-without-asset | tuning | 1/2 — failed on a reason that concludes the candidate avoided placeholders |
| chinese-request-english-repository | tuning | 2/2 |
| conflicting-licence-declarations | tuning | 2/2 |
| forge-write-confirmation | tuning | 1/2 |
| explicit-multiple-repositories | tuning | 1/2 — presented one template as applicable to both repositories |
| no-licence-declared-anywhere | holdout | 0/2 — blocks the other passes for want of a repository |

## What passed that an edit could break

`chinese-request-english-repository` and `forge-write-confirmation` both turn on what the handoff claims was checked; a sentence about reporting verification touches both.
