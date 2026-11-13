# Star lists — iteration 1 gate

No edit was made, so there is no gate to apply.

| | Before |
| --- | --- |
| tuning | 5/6 |
| holdout | 0/2 |

The one tuning failure, `bare-machine`, asks a text-only candidate for an executed command. That is the case's limit, not the skill's; it needs an `execution` block or an expectation about what the skill says it will run.

The holdout failure — applying without waiting for a yes — is real and is the most important behaviour this skill has. No edit may be aimed at it. Fixing it means promoting `confirm-before-apply` into tuning and writing a new holdout for that surface first, in a separate commit.
