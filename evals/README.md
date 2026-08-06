# Evaluation cases

One suite per published skill, at `evals/<skill>/evals.json`.

```bash
python3 scripts/run-evals.py --check           # structure, coverage, and hand-offs
python3 scripts/run-evals.py --report email    # one skill's cases, ready to paste
```

## What is and is not automated

Whether a skill fires is decided by a model, so nothing in this repository scores
a case. `--check` enforces the part that rots without anyone noticing: every
published skill has a suite, each has at least three triggers and two
non-triggers, ids are unique, and every stated hand-off names a skill that
actually exists.

Scoring is manual. Run `--report`, put the prompts to a fresh agent with the
skills installed, and record what happened. `evals/email/iteration-1/` is what
that looks like when it has been done.

## Sections

- **`triggers`** — prompts the skill must fire on. Cover the phrasings named in
  its `description`, in every language that description lists.
- **`non_triggers`** — prompts it must stay out of. Set `routes_to` when another
  published skill should take it instead; that is the boundary between two
  descriptions, written down where both can be checked against it.
- **`behaviors`** — what the skill must do once it has fired. Each carries
  `expectations`, graded individually.

`non_triggers` is the half that matters. A skill that fires on everything scores
perfectly on its own triggers, and the cost lands on whichever skill it took the
prompt from — which is invisible from inside either suite.
