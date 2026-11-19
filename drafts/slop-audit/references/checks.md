# The ten checks

Each check names its pyramid layer, what to look for, its bound, and its scoring. Timestamps point to the talk (https://www.youtube.com/watch?v=O_zcc6Xl12g). Scores and evidence rules are defined in `SKILL.md`.

## Layers 1–2: code and static checks

### 1. Corrections become checks (3:12, 9:10)

Every correction the team has given an agent twice should now be a deterministic check.

- Sources, in order: the rule register or rules contract found in reconnaissance; `AGENTS.md`, `CLAUDE.md`, `.claude/rules/`, skills; review comments on the last 50 merged PRs (`gh pr list --state merged -L 50 --json number`, then `gh api repos/{owner}/{repo}/pulls/{n}/comments`). When review comments are empty (common in solo repositories), also read subjects of `fix` and `refactor` commits from the last 90 days. Name the sources you used in the evidence.
- When a register or contract already carries statuses (`enforced` / `ratchet` / `proposed`, or derived tiers such as hard / gated / advisory), take them as the starting point and spot-check five rows against reality; a row claiming enforcement with no running check is a finding.
- For each checkable prose rule, find its enforcing check and count current violations. Judgement-only rules are out of scope for this check.
- **2**: at least 80% of checkable rules are enforced or ratcheted. **1**: some are. **0**: corrections live only in prose.
- Output a table: rule | checkable? | enforcing check or proposed tool | violations now.

### 2. Nuanced APIs are fenced (5:26)

APIs that need judgement to use well should be banned in product code and allowed only inside a wrapper module.

- Candidates by stack:
  - React / browser: `useEffect`, raw `setTimeout` / `requestAnimationFrame` / `requestIdleCallback`, `fetch` in components.
  - Python: `except Exception` and `contextlib.suppress(Exception)`, bare `except:`, `datetime.now` / `time.time` and `uuid4` / `random` in domain code, `print` and `assert` outside tests, `# type: ignore`.
  - Django: `raw()` / `extra()` / cursor SQL, unbounded `.objects.all()` in views, business logic in views.
  - SQLAlchemy: `text()` outside the persistence layer.
  - Rust: `unwrap()` / `expect()` outside tests. Swift: force unwraps and `try!`.
- Count each per top-level layer or directory, since a call legitimate in infrastructure is a misuse in domain code.
- Bound: read three uses per directory, ten in total per API, then judge.
- **2**: the frequently misused APIs are banned by lint outside a named wrapper, and the failure message names the replacement. **1**: banned in prose, or linted without a wrapper or replacement message. **0**: neither.

### 3. Architecture is visible in paths (6:10)

Layer boundaries should be readable from directory names and enforced by an import check.

- Identify the layers (for example protocol / domain / persistence / view, server / client / shared, or main / renderer).
- Look for an enforcer: `import-linter`, ruff `flake8-tidy-imports` banned modules, `eslint-plugin-boundaries`, `dependency-cruiser`, Rust crate or module visibility, or an architecture test.
- With an enforcer in CI, its green run is the evidence; list violations only when it reports some. Without one, find forbidden-direction imports with `rg` and list up to ten with `file:line`.
- **2**: layers map to directories and an enforcer in CI forbids the wrong direction. **1**: layers by convention only. **0**: no clear layers.

### 4. Comments do not justify workarounds (7:00–8:54)

Comments that excuse a workaround teach the next agent to copy it.

- Search comment lines and docstrings only, in the repository's comment language. English example: `rg -n '^\s*(#|//|\*).*\b(workaround|for now|temporary|hack|quick fix|stopgap)\b'`; add the equivalents for other languages in use (for Chinese: 暂时, 临时, 绕过). Also list `TODO` / `FIXME` / `HACK` without an issue reference.
- Classify each hit: (a) a real architecture clash with a root-cause fix, (b) stale, (c) a constraint that should be a lint rule. Then count copies of the same workaround pattern elsewhere.
- **2**: none, or each links a tracked issue with a removal condition and a check enforces that (for example ruff `TD002` / `TD003`). **1**: ten or fewer copies of any one workaround pattern. **0**: more than ten copies of one pattern.

## Layer 3: verification

### 5. Feature map exists (10:16)

A list of every user-facing feature with its entry path gives agents and humans one vocabulary.

- Repositories with a UI: look for a feature map or sitemap that names features the way users do, with entry paths (URL or clicks), owning source files, and how to verify each.
- API-only repositories: a generated operation inventory (OpenAPI snapshot, tool or CLI census) plays this role.
- Check whether CI fails when a new route, page, or operation is added without updating it.
- **2**: exists, maps features to entry paths, and CI checks it against the code. **1**: exists but drifts or is unchecked; or, for a UI repository, only an operation inventory exists. **0**: none.

### 6. Agents can run and observe the app (10:37)

Agents should verify a change by running it, through a reusable, tested driver.

- UI repositories: a script or CLI that starts the app, opens a named feature, and captures screenshots, console errors, or failed requests.
- API repositories: a script or test that starts the service, calls a named endpoint or tool, and records the response.
- Sample the last 30 merged PR bodies; count those carrying command output, a screenshot, or a recording. Note whether a PR template asks for verification.
- **2**: a tested driver exists and at least half the sampled PRs carry its evidence. **1**: a driver exists but evidence is rare, or verification is ad hoc. **0**: none.

### 7. Complex flows have a reviewable state model (13:02)

The hardest user flow should exist as a state machine someone can review.

- Pick the flow with the most states (auth, sync, payments, notifications, job lifecycle). Look for a state chart, a transition table, a state enum with explicit transitions, or a model (XState, TLA+).
- Bound: read the owning module and its tests only; list at most five states and five events. Ask the user for intended behaviour before calling a difference a bug.
- **2**: an explicit state model exists and a test asserts the legal and illegal transitions. **1**: implicit in code, with no gaps found within the bound. **0**: implicit, with gaps found. Use `not assessed` when the bound runs out before the states are clear.

### 8. Core invariants are tested as properties (10:50–11:45)

Invariants such as idempotency, tenant isolation, or balance totals need property-based or model checking, not only examples.

- Take the five most important invariants from the repository's docs or ADRs. When none are written down, propose five from the domain and mark them "proposed".
- For each, look for a property-based test (`hypothesis`, `fast-check`, `proptest`, parameterized Swift Testing with generated inputs), a model check, or at least an integration test.
- **2**: the top invariants have property or model tests in CI. **1**: example or integration tests only. **0**: untested.

## Layer 5: automation readiness

### 9. Trust metrics (13:32)

Measure whether velocity is costing quality.

- Window: the last 90 days. Commands:
  - merged PRs: `gh pr list --state merged --search 'merged:>=YYYY-MM-DD' -L 1000 --json number,createdAt,mergedAt`; confirm the oldest item predates the window or the list was truncated;
  - reverts, by subject only: `git log --no-merges --since=90.days --format=%s | grep -cE '^[Rr]evert'`;
  - CI first-run pass rate: `gh run list --workflow <file> --event pull_request -L 300 --json conclusion,attempt`, attempt 1 only, cancelled runs excluded;
  - median open-to-merge time, from the PR list.
- Read each reverted or reworked PR and name the lint or verification that would have caught it.
- **2**: the metrics are recorded somewhere repeatable (a file, dashboard, or scheduled job), the revert rate is at or under 1%, and each revert traces to a check that now exists. **1**: measurable but not recorded, or recorded but not acted on. **0**: not measurable.

### 10. Outer loop readiness (16:21)

An automated loop (release fuzzing, bug-fix PRs) helps only once checks 1–8 are strong; before that it multiplies slop.

- Compute the average of checks 1–8, to two decimals, leaving out `n/a`, `not assessed` and `blocked`.
- List the loops that already exist (scheduled audits, fuzzing, auto-fix) and the prerequisites a post-release fuzz loop needs (feature map, driver, verification evidence, low revert rate), marking which are met.
- **2**: average at least 1.5 and a loop exists. **1**: average at least 1.5 with no loop yet; or a loop exists while the average is below 1.5, which the report flags as "loop running on weak foundations". **0**: average below 1.5 and no loop; recommend strengthening checks 1–8 first.
