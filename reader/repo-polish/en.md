`repo-polish` starts from one premise: how a repository should introduce itself is answered by its own files, not by its name. So every pass reads the evidence before it writes a line.

## Read first, then write

Build configuration and lockfiles give the stack and its versions. The task runner gives the commands to get started. The CI configuration gives the checks a contributor has to pass. The commit history gives the convention the project actually uses. A fact it cannot find is left in brackets for you to fill rather than guessed — an invented install command is worse than none, because a reader will run it.

## Seven things treated as one

The README, the banner, `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, the forge's description field and its topics all answer the same question: what is this, can I use it, where do I go next.

So what it is gets settled once. The centred line in the README, the description on the forge, and the `description` in the package manifest are the same sentence rather than three versions of it. Those three disagreeing is the most common form of decay: the README describes the project as of three rewrites ago and the forge description stopped earlier still.

## Two rules it will not bend

**It never picks a licence.** It reconciles what is already declared, and where `LICENSE` and `package.json` disagree it stops and reports rather than resolving in favour of the more permissive one.

**Anything written to the forge is shown first.** The description and topics leave the machine and never appear in a diff, so it prints the exact values and waits. When it cannot write them it reports itself blocked and gives you the commands, rather than claiming a field was set.

## What it does not do

It does not write API reference documentation, changelogs, release notes or marketing landing pages, and it does not touch the source code.
