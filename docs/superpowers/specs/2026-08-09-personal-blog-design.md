# Personal Blog Skill Design

## Purpose

Add `personal-blog` to the existing `writing` plugin. The skill must help a writer research, plan, draft, revise, and polish long-form blog posts without imposing a generic internet-marketing structure or inventing the writer's life, opinions, emotions, evidence, or citations.

The published command is `/writing:personal-blog`. A finished article is returned as raw Markdown unless the user asks for a different artefact such as an outline, research notes, or editorial feedback.

## Scope

The skill supports five modes:

| Mode | Use |
|---|---|
| `explainer` | Explain an object, system, event, or concept accurately. |
| `idea-essay` | Develop a philosophical, social, life, or argumentative idea. |
| `personal-essay` | Shape experiences and reflections supplied by the writer. |
| `review` | Review a book, film, television work, game, album, or other cultural work. |
| `technical` | Produce a technical article, tutorial, architecture explanation, or engineering post. |

The skill may create a new piece or work on an existing note, outline, section, or draft. It is not for email, chat messages, repository documentation, marketing copy, fiction, or academic papers.

## Routing

Infer the mode from the requested artefact and the source material. State the selected mode only when doing so helps the user review an outline or plan. If a piece genuinely crosses modes, select one primary mode and borrow only the necessary checks from a secondary mode.

Do not turn every request into a full drafting workflow. Return the artefact requested: research for a research request, an outline for an outline request, editorial findings for a review request, and an article for a drafting request.

## Workflow

1. Build a brief from the topic, intended reader, purpose, source material, requested artefact, language, and constraints already present in the request or workspace.
2. Select the primary mode and its structural pattern.
3. Establish a voice basis from supplied writing samples, notes, or the existing draft. If none exists, use a neutral provisional voice and avoid personal claims.
4. Separate claims into supplied personal material, verifiable external claims, interpretation, and open gaps.
5. Research only the claims that need external support. Prefer primary sources for technical and current claims, verify every citation, and preserve disagreement where sources conflict.
6. Choose a structure that serves the mode and thesis. Do not require a hook, three-part body, recap, or call to action.
7. Draft or edit while preserving the writer's facts, position, uncertainty, and observable voice.
8. Run a mode-specific integrity pass and return the requested artefact in raw Markdown.

## Voice Contract

When 5–10 representative samples are available, derive a working voice profile from observable features: point of view, sentence rhythm, paragraph movement, vocabulary, humour, directness, use of questions, transitions, code-switching, and characteristic openings or endings. Treat the profile as task-local evidence, not a biography.

Never infer or invent an experience, memory, relationship, preference, belief, emotion, quotation, or outcome. When personal material is required but absent, keep the passage impersonal or insert a visible Markdown placeholder such as `[Add the moment that changed your view here.]`.

Edits must preserve intentional roughness, ambiguity, repetition, fragments, or bilingual phrasing when the samples show that these are part of the writer's voice. Avoid generic AI prose, including inflated stakes, ceremonial transitions, symmetrical lists used only for rhythm, and conclusions that merely restate the introduction.

## Mode Contracts

- `explainer`: define scope early, build a correct mental model, distinguish analogy from mechanism, and expose limitations or common misconceptions.
- `idea-essay`: lead with a real tension or question, develop a defensible thesis, include serious counterpressure, and allow an open ending when the argument warrants one.
- `personal-essay`: use only supplied events and feelings, organize by emotional or conceptual movement rather than compulsory chronology, and leave factual gaps visible.
- `review`: distinguish description from evaluation, establish criteria through the work itself, avoid plot summary as a substitute for criticism, and mark spoilers when relevant.
- `technical`: verify commands and code where tools permit, state versions and assumptions, explain trade-offs and failure modes, and never claim a result that was not observed. A more specialized installed technical-writing skill may assist, but this skill's voice, evidence, and output contracts remain authoritative.

## Shared Writing Rules

The existing `writing/shared` files remain part of every writing skill. Their message-specific rules must be explicitly scoped to messages so that email and tempering retain their current behavior while blog articles are not constrained to message length, channel shape, or a final request.

Universal shared rules continue to apply: preserve supplied facts, match the writer's language, remove empty institutional filler, and use structure only when it carries information.

## Files

- `plugins/writing/skills/personal-blog/SKILL.md`: routing, workflow, evidence rules, and output contract.
- `plugins/writing/skills/personal-blog/references/modes.md`: detailed mode recipes and integrity checks.
- `plugins/writing/skills/personal-blog/references/voice.md`: voice-profile method, anti-fabrication rules, and worked examples.
- `plugins/writing/skills/personal-blog/agents/openai.yaml`: Codex-facing metadata.
- `evals/personal-blog/evals.json`: trigger, non-trigger, and behavior cases.
- `plugins/writing/shared/tone.md` and `plugins/writing/shared/format.md`: scope message-only rules, then vendor them into all writing skills.
- Repository manifests, registries, bilingual READMEs, `skills.sh.json`, and version-bump configuration: register the new skill through the repository scaffold.

No runtime script or asset is required. The difficult parts are judgement and evidence handling, so executable prose and evaluation cases are the appropriate controls.

## Evaluation

Evaluation cases must cover all five modes; writing from sparse personal notes; deriving voice from samples without inventing biography; current technical research with verified citations; raw-Markdown-only delivery; editing without erasing intentional style; and non-triggers for email, chat tempering, README work, marketing copy, fiction, and academic papers.

Repository acceptance requires description checks, eval registration checks, shared-file synchronization, repository validation, Ruff, ShellCheck, version audit, CI pin checks, and a clean diff check.
