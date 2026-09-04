# Evaluation cases

One suite per published skill, at `evals/<skill>/evals.json`.

```bash
python3 scripts/run-evals.py --check                       # structure, coverage, and hand-offs
python3 scripts/run-evals.py --report email                # one skill's cases, ready to paste
python3 scripts/run-evals.py --report email --split holdout  # just the gated ones
```

## What is and is not automated

`--check` enforces the part that rots without anyone noticing: every published
skill has a suite, each has at least three tuning triggers, two tuning
non-triggers, and one held-out case per populated section, ids are unique, and
every stated hand-off names a skill that actually exists.

It also fails when two descriptions claim the same Chinese trigger phrase and
neither suite says which skill should win a prompt carrying it. That check lives
here rather than in `check-descriptions.py` because settling it needs both
halves: the descriptions competing for the phrase, and the `routes_to` that
decides between them. `check-descriptions.py` counts a shared run in words, and
Chinese is written without spaces — a whole phrase reaches it as one token, so
its ceiling of seven is never approached in the language most of these
descriptions use to name their triggers.

Scoring is not manual. `--run` asks a model which skill a prompt should route
to, given every published description and nothing else, and `--run-behaviors`
generates a response per behavior case and grades it against its expectations —
mechanically where a validator exists, by judge otherwise. Both need the scoped
gateway key and run in the local preflight:

```bash
LITELLM_EVALS_API_KEY=... bash scripts/run-evals-local.sh email
```

The hand-run remains the higher-fidelity path, and it is what an iteration uses:
`--report`, the prompts put to a fresh agent with the skills actually installed,
and what happened written down. `evals/email/iteration-1/` is that, done.

## Splits

A case carrying `"holdout": true` belongs to the gate; everything else belongs
to tuning. The tuning cases drive an edit to `SKILL.md`; the held-out cases
decide whether it is kept, and no edit may be aimed at one.

Without that separation a suite cannot tell a fix from an overfit. `email`
iteration-1 reached 100% by narrowing wording in response to `ambiguous-reply`
and then re-scoring `ambiguous-reply` — a real number that measured nothing
about generalisation, and nothing here could see the difference at the time.

`--split tuning` and `--split holdout` select one side; the default is `all`,
which is what CI and the weekly run score. The loop, the selection rule, and the
edit budget are in [ITERATION.md](ITERATION.md).

## Sections

- **`triggers`** — prompts the skill must fire on. Cover the phrasings named in
  its `description`, in every language that description lists.
- **`non_triggers`** — prompts it must stay out of. Set `routes_to` when another
  published skill should take it instead; that is the boundary between two
  descriptions, written down where both can be checked against it.
- **`behaviors`** — what the skill must do once it has fired. Each carries
  `expectations`, graded individually.
- **`holdout`** — `true`, or absent. At least one per populated section, chosen
  as the surface the tuning cases cover least; never on a `routes_to` boundary,
  which is what a description edit already aims at. `--check` holds both rules.

`non_triggers` is the half that matters. A skill that fires on everything scores
perfectly on its own triggers, and the cost lands on whichever skill it took the
prompt from — which is invisible from inside either suite.
