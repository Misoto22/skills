# Rejected edits — iteration 2

Two candidates dropped, both on a static reading of the suite.

## Collapse the Chinese trigger list from five phrases to three

- **Aimed at** — the audit's "one trigger per branch". `清理一下` and `收拾一下仓库`
  are one branch; `清掉合并过的分支` and `删掉没用的分支` are close to one.
- **Dropped because** — four of `cleanup`'s six routing cases are Chinese, and
  they land across the whole list: `清理一下仓库，收拾下没用的分支` needs `清理一下`
  *and* the `收拾` phrasing, and the held-out `远程还留着一堆合并过的分支，清一下`
  needs `清理远程分支` and `清掉合并过的分支`. The English list is where the
  duplication was free to remove, and that is where it was removed.
- **Do not re-propose as** — "the Chinese phrases repeat each other." They
  repeat each other less than they look like they do; the cases are the evidence.

## Also cut the `__pycache__` example

- **Aimed at** — a further 47 characters, on the reading that an example belongs
  in the body.
- **Dropped because** — "ignored residue a move stranded" without it is a phrase
  no one can route on. The example is the only thing in that clause that names a
  concrete artefact, and `residue` is this skill's own coined term rather than a
  word the model already holds. Cutting it would have taken the description to
  -183, past the audit's range, by removing the half that does the work.
- **Do not re-propose as** — "the body defines residue anyway." The body is not
  loaded when the routing decision is made.
