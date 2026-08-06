# Optional Humanizer integration

The canonical upstream project is [blader/humanizer](https://github.com/blader/humanizer). This skill was tested against Humanizer `v2.9.1`. Humanizer remains a separate optional skill; this repository does not copy or vendor its pattern catalog.

## Policy behavior

- `disabled`: do not invoke Humanizer.
- `optional`: use an available compatible Humanizer skill for prose, otherwise apply the fallback checklist and continue.
- `required`: do not silently omit it. If no compatible Humanizer is available, return `blocked` with setup guidance; drafting may continue only after the user changes policy or installs it.

Follow the upstream repository's current installation instructions for a global or project-local skill installation. Do not assume a fixed home directory or package-manager layout.

## Safe invocation

1. Extract protected facts from the approved source before rewriting.
2. Give Humanizer only the prose body, not transport instructions, authorization metadata, recipient policy, hashes, or credentials.
3. Keep the requested tone and meaning; Humanizer cannot authorize send or alter recipients.
4. Compare every protected fact exactly after the rewrite.
5. On any change, block the send attempt. Return to the approved facts, create a new draft, render HTML again, and rerun the complete validator. Do not silently replace one changed number and reuse the old validation.

Fallback checklist when optional Humanizer is unavailable:

- apply `shared/tone.md` at the skill root, which carries the filler, inflation, and unearned-warmth rules;
- prefer direct, specific sentences;
- vary sentence length only when it improves natural flow;
- keep every protected string unchanged.

Humanizer version differences must never weaken the email policy or validation pipeline.
