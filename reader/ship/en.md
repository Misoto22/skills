Shipping a change is a sequence everyone already knows: branch, test, commit, open a pull request, wait for CI, merge, tidy up. The cost is never in knowing it — it is in the step that gets skipped at five in the afternoon. `ship` runs the whole sequence and refuses to skip anything silently.

## The preflight decides the run, and says so first

Before touching anything it inspects the repository and prints an execution plan marking every downstream step `RUN` or `SKIP`. What it found decides the plan: whether a test command exists, whether the project declares CI, whether there is already an open pull request for this branch.

That plan is the contract for the rest of the run — a step marked `SKIP` does not run, and no step outside the plan is invented. `--dry-run` prints it and stops.

A clean tree on the base branch with nothing unpushed and no open pull request exits right there. Nothing to ship is a result, not a failure.

The one case that looks like nothing and is not: commits sitting on your local base that the remote does not have, because somebody committed to `main` by hand. Reporting "nothing to ship" over those leaves work that only `git log` will ever mention, so the run branches off and carries them.

## Nothing is inferred that is actually a judgment

The test command, the lint command and the version bumper are detected from what the project itself declares — a script in `package.json`, a `justfile` target, a `Makefile` rule. Detection stops at the first match, and a project that declares none simply skips that step and says so.

Detection is not the same as deciding. Whether a change is a release is the author's call and not a property of the diff, so the version bumper runs only when `--bump` is passed. Found but not asked for is reported as skipped rather than helpfully run.

## The last moment before it becomes public

A secret pushed to a remote is compromised even after a force-push removes it, so the gate sits immediately before staging — over the content of the change rather than over file names, and over untracked files too, because `git diff` never mentions those and they are exactly where a fresh `config.local.json` with a live token would be.

A match stops the run and asks. It does not decide alone: fixtures and documentation legitimately contain credential-shaped strings, so what you get is the file, the line, and a question.

Staging is by explicit path. Never `git add -A` — every ambiguous untracked file is collected into one prompt and asked about in a single round trip, rather than swept in or asked about one at a time.

## Waiting for CI, honestly

"No checks reported" means two different things minutes apart. A pull request opened seconds ago reports none because GitHub has not registered the run yet, and that reads identically to a repository with no CI at all. Merging on that reading ships without the checks the project wrote.

So the preflight already established which case this is. Where a workflow declares a trigger, the run re-polls for up to a minute before concluding there are none — and if nothing registers, the report says `CI skipped` with the count of workflows that were declared. That line is the difference between a check that was green and a check that never ran.

A merge state that needs a person — a required review missing, a non-required check red, a conflict with the base — stops and asks. Conflicts are never auto-resolved.

## What it will not do

It does not tag a release, publish a package, or deploy: those are decisions that follow a merge rather than parts of it. It will not write a commit message without pushing it. It never force-pushes the base branch, never resolves a merge conflict on your behalf, and never removes the worktree the run is standing in — that one is reported as kept, because the deletion cannot be undone from inside it.
