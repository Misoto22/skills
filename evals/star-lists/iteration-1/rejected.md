# Star lists — iteration 1 rejected

## Restore: show the diff, including lists it deletes, and wait for a yes

- **Aimed at** — an audit reading of the Restoring section, which runs `diff` then `apply --yes` with no explicit confirmation step.
- **Dropped because** — the case written for it, `restore-shows-deletions`, passed 2/2 before any edit. An iteration starts from a measured failure, and there was none to move.
- **Do not re-propose as** — "Restoring: wait for a clear yes before `apply --yes`" without a failing tuning case first.
