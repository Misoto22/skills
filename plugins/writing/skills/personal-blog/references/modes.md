# Mode recipes

Choose the primary mode from the article's job, not merely its topic.

| Mode | Use when the article must |
|---|---|
| `explainer` | Give a reader an accurate mental model of an object, system, event, or concept. |
| `idea-essay` | Develop an argument or inquiry about a philosophical, social, or everyday-life idea. |
| `personal-essay` | Shape experiences and reflections the writer supplied. |
| `review` | Evaluate a cultural work rather than merely describe it. |
| `technical` | Teach, diagnose, compare, or explain an engineering system or practice. |

## Explainer

- **Evidence:** Use verified definitions, mechanisms, measurements, and examples.
  Label an analogy as an analogy; it is not evidence for how the mechanism works.
- **Structure:** Establish scope and the reader's starting point, build the mental
  model in dependency order, then expose limitations and common misconceptions.
- **Integrity check:** Can the reader distinguish what happens, why it happens,
  and where the model stops being accurate?
- **Avoid:** The generic surprising-hook, list-of-facts, recap pattern, or an
  analogy stretched until it replaces the mechanism.

## Idea essay

- **Evidence:** Support factual premises externally. Treat the thesis, values,
  and synthesis as argument rather than fact, and distinguish the writer's stated
  beliefs from the draft's provisional reasoning.
- **Structure:** Begin from a real tension or question, develop a defensible
  position, test it against serious counterpressure, and end where the inquiry
  warrants—even if that ending remains open. Make the final move a narrowed
  position, residual tension, or open question. When the prompt rejects a
  motivational ending, keep the last paragraph inside the inquiry; direct
  reassurance, permission, advice, or a suggested next step fails that request.
- **Integrity check:** Does the strongest objection alter, narrow, or sharpen the
  argument rather than appear as a token paragraph?
- **Avoid:** Three neat reasons followed by a motivational lesson or compulsory
  advice to the reader.

## Personal essay

- **Evidence:** Use only events, relationships, memories, quotations, feelings,
  and outcomes supplied by the writer. External context may be researched, but
  it cannot fill a personal gap. Before drafting, extract a personal fact
  inventory. For every concrete sentence about the writer or anyone in the
  writer's life, regardless of pronoun, map only the fields it actually
  asserts—actor, action, time, place, feeling, outcome, or another claimed
  detail—to exact supplied fragments. Rewrite any field without a match
  impersonally or leave a visible gap.
- **Structure:** Arrange supplied scenes and reflection by emotional or conceptual
  movement. Use chronology only when chronology carries the meaning. When the
  notes lack scenes or bridges, keep the result visibly partial:

  ```markdown
  Close restatement of a supplied fact.

  [Add the specific missing scene or bridge.]

  Close restatement of a supplied reflection.
  ```
- **Integrity check:** Make a sentence audit before delivery. For every concrete
  sentence about the writer or anyone in the writer's life, regardless of
  pronoun, map only the fields it actually asserts to exact supplied fragments.
  Rewrite any unmatched asserted field as a non-personal possibility or a visible
  bracketed Markdown gap; plausibility and thematic fit are not evidence.
- **Avoid:** A complete chronological memoir arc, invented scene-setting, or a
  manufactured epiphany that makes sparse notes look finished.

## Review

- **Evidence:** Ground description in the work and publication facts; ground
  evaluation in observable choices and clearly stated criteria. Mark spoilers
  before revealing material developments.
- **Structure:** Establish what the work attempts, examine the choices that
  produce or weaken its effects, and let the verdict emerge from that analysis.
- **Integrity check:** Is each judgement supported by something in the work, and
  is description visibly separate from evaluation?
- **Avoid:** Plot summary standing in for criticism, or a generic pros-and-cons
  list capped by a numerical verdict.

## Technical

- **Evidence:** Prefer primary documentation, specifications, source code, and
  observed tool output. State versions, environment assumptions, and the boundary
  between documented behavior and inference. When current released behavior is
  requested without a version, put the as-of date, stable release series, and a
  citation to an official current-release or status page that establishes that
  stable series as of the stated date in the article's assumptions. Cite
  documentation under the same version segment; historical release notes or a
  versioned documentation URL alone do not establish current stable status. Use
  development-branch documentation only when the article explicitly covers
  unreleased behavior.
- **Structure:** Frame the concrete problem and system boundary, build the causal
  model, then present diagnosis or implementation choices with trade-offs,
  failure modes, and verification steps.
- **Integrity check:** For current release claims, does the article state an
  as-of date, cite an official current-release or status page establishing the
  stable series on that date, and keep framework-documentation links on that
  series? Check commands and code when tools permit. Never report a test,
  benchmark, deployment, or command result that was not observed; label unrun
  steps as instructions or expected results.
- **Avoid:** A context-free install-and-happy-path tutorial, or a universal best
  practice that hides version, workload, and operational trade-offs.
