`sessions` answers the moment you sign in with your other account and the sidebar is suddenly almost empty. Nothing was deleted. Claude's desktop app keeps a separate conversation index for each account it has been signed in as, and it shows you only the one belonging to whoever is signed in now. This unions those indexes, so whichever account you use, you see the whole history.

## Nothing was lost, and you can prove it

Two stores hold a conversation, and only one of them has ever heard of accounts.

The conversation itself — every message, every tool call — is a JSONL file under `~/.claude/projects/`, filed by the directory you were working in. Open one and there is no account field anywhere in it. That is why `claude --resume` in a terminal has been listing all of your conversations the whole time, no matter which account is signed in.

What the sidebar reads is a second, much smaller set of files: one index entry per conversation, stored under a path that begins with your account's identifier. Sign in as a different account and the app reads a different directory. The conversations are still on disk, in full, untouched.

So the fix is much smaller than the symptom. Nothing needs recovering; the lists need merging.

## What it does

It copies each account's index entries into every other account's index.

```
Session index ~/Library/Application Support/Claude/claude-code-sessions
  account bc95701b…    36 conversations  lands in ee9e5ec5…
  account cb24d9c9…   358 conversations  lands in c04cc789…
  account d58bde8d…    81 conversations  lands in 2618534f…  <- signed in

Plan: 720 entries to copy into 3 account index(es), +114.3MB
  skipped 224 whose transcript is gone
```

That report is the whole of a default run. It writes nothing until you pass `--apply`, because 114MB and three directories is not a decision to make on someone's behalf without showing them the number first.

## What it refuses to do

**It never deletes.** Every run only adds files, and it records each one it added. `--undo` removes exactly those paths — not files the app wrote, not entries a previous merge already reconciled.

**It skips entries whose conversation is gone.** An index entry can outlive its transcript. Copied around, it becomes a row in your sidebar that opens to nothing, which is worse than not being there. Those are counted in the report and left behind unless you ask for them.

**It runs again cleanly.** New conversations only land in the index of the account you were signed in as, so this is a thing you re-run, not a thing you do once. A second run with nothing to do plans zero copies and says so.

## The restart

A merge does not appear until the desktop app restarts. The app reads this index when it starts and does not look at the directory again while it is running.

That matters more than it sounds, because restarting interrupts whatever conversations are still running. The run tells you to restart rather than doing anything about it, and checking what is live first is worth the ten seconds.
