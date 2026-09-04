`ship` takes a change from your working tree to a merged pull request: branch off, run the project's own tests, commit, open the pull request, wait for CI, merge, then clean up the worktree. Which steps ran, which were skipped, and why, all go in the report.

```steps
{
  "steps": [
    {
      "n": "00",
      "label": "Preflight",
      "note": "always — prints the plan",
      "anchor": true
    },
    {
      "n": "01",
      "label": "Branch off base",
      "note": "on the base branch, with something to ship"
    },
    {
      "n": "02",
      "label": "Test & lint",
      "note": "only what the project declares"
    },
    {
      "n": "03",
      "label": "Commit",
      "note": "secrets gate before staging"
    },
    {
      "n": "04",
      "label": "Pull request"
    },
    {
      "n": "05",
      "label": "CI",
      "note": "re-polls before concluding there are none"
    },
    {
      "n": "06",
      "label": "Merge"
    },
    {
      "n": "07",
      "label": "Worktree cleanup",
      "note": "never the one this run is standing in"
    }
  ],
  "caption": "Preflight marks every step RUN or SKIP, and the run follows that plan exactly. A clean tree on the base branch with nothing unpushed and no open pull request exits at step 0.",
  "label": "The eight steps ship runs, and what each one depends on"
}
```

## The preflight and the execution plan

Step 0 is a preflight. It reads the repository's state — which branch you are on, whether the tree is clean, whether there are unpushed commits, whether this branch already has an open pull request — and prints an execution plan marking every later step RUN or SKIP. The rest of the run follows that plan exactly: a step marked SKIP does not run, and no step outside the plan is added along the way. `--dry-run` prints the plan and stops.

The reason for the plan is that "ship" means different things in different states: uncommitted changes on the base branch, an open pull request on a feature branch, and a clean tree whose local base carries commits the remote does not are three different paths. Settling the state first means nothing downstream has to guess.

A clean tree on the base branch with nothing unpushed and no open pull request exits at step 0 and reports that there is nothing to ship. One case looks like that and is not: somebody committed to `main` by hand, so the local base carries commits the remote does not. That branches off and carries them rather than reporting no work.

## Where the test, lint and version commands come from

The test command, the lint command and the version bumper are read from wherever the project declares them — a script in `package.json`, a `justfile` target, a `Makefile` rule, and the CI configuration. Matching stops at the first hit; a project that declares none skips that step, and the report says skipped rather than passed. A failing test is retried at most twice before the run stops and asks.

The version bumper is the exception: found or not, it runs only when `--bump` is passed. Whether a change is a release is the author's call rather than a property of the diff. Detected and not asked for is reported as skipped.

## The credential scan before the commit

A scan runs before anything is staged. It reads the content of the change rather than file names, and it covers untracked files. Untracked files have to be read separately because `git diff` never mentions them, and a freshly created `config.local.json` holding a live token is exactly that case.

A hit stops the run and asks. It does not decide alone: fixtures and documentation legitimately hold credential-shaped strings, so what comes back is the file, the line and a question.

Staging is by explicit path, never `git add -A`. Untracked files it cannot classify are collected into a single prompt and asked about in one round trip.

## Waiting for CI

"No checks reported" means two different things minutes apart. A pull request opened seconds ago reports none because GitHub has not registered the workflow run yet, and that looks identical to a repository with no CI at all. Merging on the second reading ships without the checks the project wrote.

So the preflight has already established whether the repository declares a workflow. Where one is declared, the run re-polls for up to a minute before concluding; if nothing registers, the report says `CI skipped` with the number of workflows declared. Where none is, step 5 is skipped outright.

Merge states that need a person — a missing required review, a failing non-required check, a conflict with the base — stop and ask. Conflicts are never resolved automatically.

## What it does not do

It does not tag a release, publish a package, or deploy; those are separate work that follows a merge. It does not write a commit message without pushing it. It does not force-push the base branch, does not resolve merge conflicts for you, and does not remove the worktree the run is standing in — that one is reported as kept, because the deletion cannot be carried out from inside it.
