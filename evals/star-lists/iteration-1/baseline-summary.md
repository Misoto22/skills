# Star lists — iteration 1 rollout

First scored run. HEAD `aa67ac1` (adds `restore-shows-deletions`), with-skill arm, 2 samples, one case per run, deepseek-default for candidate and judge, `--max-input-tokens 32000`.

| Case | Split | Before |
| --- | --- | --- |
| restore-shows-deletions | tuning | 2/2 |
| english-output | tuning | 2/2 |
| bare-machine | tuning | 1/2 — failed "runs `sh scripts/run.sh doctor` first": a text-only candidate can say it will run doctor but cannot run it |
| confirm-before-apply | holdout | 0/2 — goes from the diff straight to `apply --yes` without waiting for a yes |

## What passed that an edit could break

`restore-shows-deletions` and `english-output` both rest on "show the diff, wait for a yes"; any wording around Restoring or step 4 touches them.
