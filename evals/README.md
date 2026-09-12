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

## Experiment runs and cost boundaries

The repository gate remains free: GitHub Actions runs structural checks, unit
tests, and installation checks. It does not run model scoring. The remote Evals
workflow has no schedule and its scored job is disabled unless the repository
explicitly enables it; hosted runners cannot use the protected gateway.

Paid experiments run locally through an SSH loopback gateway and a scoped
1Password reference. They start dry and keep reports local; no command may
publish a report or spend money merely because a pull request was opened. A
shared CNY ledger reserves the worst case before a request. Observed provider
usage is evidence for the report, not permission to release an untrusted
reservation.

The execution runner may expose named fixture tools. That boundary is a
declared tool allowlist and fixture copy, not an operating-system sandbox: do
not point it at production data, user home directories, or arbitrary commands.

Create an environment file with a gateway URL and a credential-store reference;
never source a reference dotenv file straight into the SDK, and never replace
the reference with a key value:

```dotenv
LITELLM_EVALS_BASE_URL=https://gateway.example/v1
LITELLM_EVALS_API_KEY=op://vault/item/field
```

Set the placeholders once for a split run, then use the same arguments first
without `--execute`. The dry run computes the reservation and writes nothing to
the provider. `op run` resolves the reference only for the child process.

```bash
SKILL=your-skill
CASE=your-behavior-case
SPLIT=tuning
RUN=before-tuning

op run --env-file .evals.env -- python3 scripts/run-evals-experiment.py "$SKILL" \
  --case "$CASE" --split "$SPLIT" --arms both --samples 3 \
  --candidate-model deepseek-default --judge-model deepseek-default \
  --candidate-reasoning-effort none --judge-reasoning-effort none \
  --model-provenance .eval-runs/model-provenance.json \
  --max-turns 4 --max-tool-calls 4 --max-input-tokens 32000 \
  --max-output-tokens 4000 --judge-max-output-tokens 1000 --retries 0 \
  --prices evals/pricing.example.json --max-cost-cny 0.30 --budget-limit-cny 1.00 \
  --budget-ledger .eval-runs/budget.json --output ".eval-runs/$RUN.json"
```

After reviewing the printed reservation, repeat that command with `--execute`
as its final argument. The output path must be new: the runner refuses to
overwrite evidence. Run the same four-phase shape separately for
`before-tuning`, `before-holdout`, `after-tuning`, and `after-holdout`; use the
matching `--split` each time.

`--candidate-reasoning-effort` and `--judge-reasoning-effort` are optional and
omitted by default. Use them only when the selected provider and gateway
support the option. The configured DeepSeek-through-LiteLLM path accepts
`none`, which explicitly disables DeepSeek thinking mode; it is passed as the
top-level OpenAI-compatible `reasoning_effort` field. Do not assume `none` has
the same meaning or support for another provider.

`--model-provenance` records an operator-supplied mapping attestation. It never
discovers gateway internals automatically. Create it from a reviewed gateway
inventory, keeping it free of credentials:

```json
{
  "source": "reviewed gateway inventory",
  "as_of": "2026-09-12",
  "mapping_digest": "<64-character lowercase SHA-256 digest>",
  "candidate": {
    "requested_alias": "deepseek-default",
    "provider": "deepseek",
    "model": "deepseek-flash",
    "revision": "DeepSeek-V4.1-Flash",
    "deployment_id": "<reviewed deployment identifier>"
  },
  "judge": {
    "requested_alias": "deepseek-default",
    "provider": "deepseek",
    "model": "deepseek-flash",
    "revision": "DeepSeek-V4.1-Flash",
    "deployment_id": "<reviewed deployment identifier>"
  }
}
```

Read the ledger and the saved record after every execution:

```bash
jq '{limit_cny, reserved_cny, runs}' .eval-runs/budget.json
jq '{run_id, run_config, provenance, usage_trusted, actual_cost, summary}' \
  ".eval-runs/$RUN.json"
```

If a run returns nonzero, stop. Keep its record and ledger entry; when usage is
untrusted, the full reservation deliberately remains held. Diagnose the error
without retrying, then start a new output record only after the shared ledger
has enough remaining capacity. Never edit or delete a ledger entry to release a
reservation.

Run tuning and holdout as four separate records: before-tuning, before-holdout,
after-tuning, and after-holdout. Apply the gate with
`scripts/compare-eval-runs.py --before-tuning BEFORE-TUNING.json --before-holdout BEFORE-HOLDOUT.json --after-tuning AFTER-TUNING.json --after-holdout AFTER-HOLDOUT.json`.
It combines each version's two split records and compares only their
`with`-skill arms. The suite, scoring, model, and case-sample evidence must
match; tuning must improve strictly, and holdout must not fall. A missing arm,
wrong split, void sample, malformed record, or non-comparable sample set is
`inconclusive`, never a pass. Add `--benchmark PATH` to write a compact
Markdown record beside the iteration.

Claude Code's official eval feature was initialized separately with the
temporary 2.1.269 client. That initialization is not a paid run and is not
evidence that its independent scorer has passed this repository's gate.

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
  `expectations`, graded individually, and may carry an `artifact`: a JSON file
  handed to the model as evaluation data. `fixture` is the stronger form —
  the same injection, plus the draft checked against that artifact by the
  skill's registered validators. A case names one or the other.
- **`holdout`** — `true`, or absent. At least one per populated section, chosen
  as the surface the tuning cases cover least; never on a `routes_to` boundary,
  which is what a description edit already aims at. `--check` holds both rules.

## What an expectation may assert

A behavior case is scored in a text-only runner: the skill document is the
system prompt, the case prompt is the user turn, and there are no tools, no
filesystem, no git, and no image generator. **An expectation must name something
a response can carry** — a plan, a classification, a refusal, a derived value,
or produced prose. Never an effect on the world.

This is not a style preference. An expectation reading "renames only the 195
local rows" cannot be satisfied by any correct behaviour here, so the honest
answer — that the rename cannot be performed — scores as a failure, and the case
reports a skill defect that does not exist. Nineteen of eighty-three cases were
failing that way before the rule was written down.

Rewriting one is not lowering the bar. "Renames only the local rows" becomes
"scopes the operation to the local rows and to no others": the same claim about
the same decision, asked of the half of it the runner can see. Where the skill's
work is genuinely an artifact — an image, a composed board — assert the
constraint it names and the value it derives, not that it says it will comply.

A case that needs real data supplies it with `artifact`. The prompt then states
that the artifact has already passed the skill's validation step, because a skill
whose workflow opens with "run the validator" cannot run one here and will
otherwise return the validation report instead of the work. **An `artifact` must
therefore be a valid one** — generate it with the skill's own calculator. A case
that tests a refusal over a corrupt source supplies no artifact and describes the
corruption in its prompt, which is how those cases already pass.

A fail-fast preflight needs the same sentence for the same reason. `ship` opens
by stopping the run when `gh`, authentication, or a remote is missing, and none
of the three exists in this runner — so it answered with that refusal, and every
expectation phrased as an outcome failed against it. Its prompts now close with
`Environment prerequisites already passed and the state described is what
preflight read`, which is the artifact sentence in a skill that validates its
environment rather than its input.

A case that needs real tools cannot be scored here at all, and should assert the
decision rather than pretend to observe the outcome.

`non_triggers` is the half that matters. A skill that fires on everything scores
perfectly on its own triggers, and the cost lands on whichever skill it took the
prompt from — which is invisible from inside either suite.
