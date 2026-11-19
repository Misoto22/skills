# slop-audit (draft)

Unpublished. Lives under `drafts/` until it carries everything a published skill requires (see `AGENTS.md`).

## Status

- One trial run on a ~1,300-file Python service (2026-11-19). That run produced 30 pieces of feedback on ambiguous bounds and scoring; this version folds them in (scores `n/a` / `not assessed` / `blocked`, per-check bounds, exact `gh` and `git` commands, reuse of existing rule registers and derived enforcement tiers).
- The principle it audits is a rules-repository concern, not this skill's: the skill measures it, it does not define it.

## Before promotion

1. Choose the plugin. A plugin is a subject: this is repository health rather than "the loop around a change", so it likely wants its own plugin, not `dev`.
2. Scaffold with `python3 scripts/new-skill.py <plugin> slop-audit` and move this content in.
3. Write `evals/slop-audit/evals.json` with tuning and held-out cases, including a `routes_to` boundary against code review.
4. Write `reader/slop-audit/<locale>.md` for every locale and the `i18n` entries.
5. Run `python3 scripts/validate-repository.py`, `scripts/check-descriptions.py`, and `scripts/run-evals.py --check`.
6. Second trial on a repository with a UI, to exercise checks 5 and 6 on their UI branch.
