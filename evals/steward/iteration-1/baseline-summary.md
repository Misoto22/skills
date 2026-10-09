# Steward — iteration 1 rollout

## What this iteration is

The first scored run of the suite. Steward had changed under #118 (retitle's `--apply`, report line, attended mode) and #121 (desktop sessions count as occupancy).

## Rollout

Same configuration as reunite iteration 1: with-skill arm, 2 samples, `deepseek-default`, one case per run, HEAD `510f151` clean. Routing (`run-evals.py`): 11/11.

| Case | Split | Before |
| --- | --- | --- |
| unattended-proposes-titles-only | tuning | 1/2 |
| occupied-worktree-kept | tuning | 1/2 |
| merge-ledger-without-merging | tuning | 0/2 — never named the failing check, which the prompt never gave |
| vanished-checkout-continues | tuning | 1/2 |
| schedule-on-request | tuning | 0/2 — a text-only case cannot read or register a scheduler |
| one-repository-failing-does-not-stop-the-sweep | tuning | 0/2 — judge read "run `gh auth login` later" as prompting |
| dry-run-writes-nothing | holdout | 1/2 |

Three of the four zeros are the cases, not the skill: a prompt that withholds what the expectation asks for, a scheduler no text-only run can reach, and an expectation the judge reads as forbidding the very Needs-you line §6 prescribes.
