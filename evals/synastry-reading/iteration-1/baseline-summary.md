# Baseline observations — iteration 1

The rollout is the full-repository behavior scan of 2026-09-04, tuning split,
`deepseek-default` through the evaluation gateway. No edit had been made to this
skill when it ran.

```
explicit-romantic-context          FAIL   4 mechanical violations
weak-requested-domain              FAIL   6 mechanical violations + expectation 3
legacy-txt-refusal                 pass
neutral-context-omits-sensitive-domains   void — gateway returned no Markdown
explicit-family-and-work-context          void — gateway returned no Markdown
uncertain-date-only-source                void — case could not run
```

One pass in three scored cases. Three of six were lost to the gateway rather
than scored, which is the tax on this suite: its drafts are long.

This skill is the only one in the repository whose behavior cases are worth
arguing about without qualification. Its cases carry a `fixture`, so the model
receives the artifact *and* the validated ledger it is graded against, and the
failures below come from `validate_reading.py` rather than from a judge's
opinion. Nothing here is a matter of taste.

## What failed

```
reading contains no inline evidence tokens
substantive paragraph lacks valid evidence
substantive paragraph requires conditional language
deterministic prediction language is forbidden
compatibility score or rating language is forbidden
measurement does not match paragraph evidence
```

`SKILL.md` states every one of these rules. It states none of them in a form the
model can execute.

> Make every substantive paragraph conditional and cite one or more ledger
> evidence IDs inline.

The validator accepts exactly one citation shape, `[E-ASPECT-9DAF]` or
`[E-OVERLAY-3096]` — the bracketed token that opens each ledger entry's
`citation` field. **That string appears nowhere in `SKILL.md` or in any of its
three references.** `output-template.md` writes `<Conditional synthesis with
inline evidence ID(s).>`, which tells a model to cite and leaves it to guess the
form. It guessed prose, and `reading contains no inline evidence tokens` is what
that looks like from the validator's side.

"Conditional" is the same shape of gap. The validator wants one of a fixed set of
hedging words in the paragraph, and refuses a fixed set of deterministic ones —
`will` among them, which ordinary prose reaches for without meaning a forecast.
The skill says "make it conditional" and "do not predict events", and leaves both
lists unstated.

## What passed that this edit could break

- `legacy-txt-refusal` — the one scored pass. It refuses a TXT source outright,
  and a refusal has no substantive paragraph, so the added vocabulary rules
  should not reach it. If they do, the edit has grown into the refusal path.
- `adversarial-label-is-data` (held out) — must keep treating a hostile display
  label as data. The edit tells the model to copy tokens character for character
  from the ledger, and the held-out case's artifact carries a label that asks to
  be obeyed. Copying *from the ledger* is the whole safeguard; if the wording
  reads as "copy what the artifact says", the edit has broken the one case it
  was most important not to touch.

The second risk is why the edit says the token is copied from the ledger entry
rather than from the artifact.
