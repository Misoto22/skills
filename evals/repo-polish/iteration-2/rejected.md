# Repo polish — iteration 2 rejected

## Report an unrunnable render check as not run

- **Aimed at** — `render-check-unpushed`, whose first sample never mentioned the rendered-page check (README §1 in SKILL.md, after "In short").
- **Dropped because** — the gate: tuning fell 7/12 → 5/12. The targeted expectation ("reports the render check as not run, and says why") moved from one miss to none, but four new failures appeared, all on negatively worded expectations ("Does not …") whose judge reasons describe a passing answer — `render-check-unpushed` #3 twice and `chinese-request-english-repository` #3 twice. The judge inverts "Does not" criteria often enough to swamp a one-edit signal at n = 2.
- **Do not re-propose as** — the same sentence against the same cases. Rephrase the negative expectations positively first (a suite change, its own commit and baseline), then retry.
