`reunite` answers the moment you sign in with your other account and the sidebar is suddenly almost empty — or the moment you archive or delete a conversation under one account and it is still sitting in the other one's sidebar. Claude's desktop app keeps a separate conversation index for each account it has been signed in as, shows you only the one belonging to whoever is signed in now, and writes every change into that one only. This makes every account hold the same conversations, in the same state, byte for byte.

## Nothing was lost, and you can prove it

Two stores hold a conversation, and only one of them has ever heard of accounts.

The conversation itself — every message, every tool call — is a JSONL file under `~/.claude/projects/`, filed by the directory you were working in. Open one and there is no account field anywhere in it. That is why `claude --resume` in a terminal has been listing all of your conversations the whole time, no matter which account is signed in.

What the sidebar reads is a second, much smaller set of files: one index entry per conversation, stored under a path that begins with your account's identifier. Sign in as a different account and the app reads a different directory. The conversations are still on disk, in full, untouched.

So the fix is much smaller than the symptom. Nothing needs recovering; the lists need aligning.

## What it does

For each conversation it takes the copy you touched last and makes it every account's copy — creating it where an account has none, overwriting it where an account's copy is stale.

```
Plan: align 5 account index(es)
  891 copies to create, +47.6MB
  6912 copies to overwrite with the canonical copy
      103 change title
     2702 change isArchived
       17 change isStarred
     5536 change other fields only the app reads
  0 copies to remove — 0 conversations deleted under one account
  110 conversations have no transcript left; they are kept, archived
```

That report is the whole of a default run. It writes nothing until you pass `--apply`, because thousands of rewritten files is not a decision to make on someone's behalf without showing them the numbers first. After writing, it rescans and checks that every conversation really is identical in every account, and says so — or names the ones that are not.

## Archives and deletions travel too

Archiving decides what the sidebar shows, so it is not left to "whichever copy is newest". Every run records what each account held and what was archived; the next run compares against that. An archive or unarchive you made under one account reaches the others. A conversation you deleted under one account is removed from all of them, and is never copied back — which is what used to happen, and why a cleaned-up sidebar kept refilling.

The first time it runs there is no record to compare against, so copies that disagree settle on archived. Hiding is the recoverable way to be wrong. Entries whose transcript is gone are kept so the lists match, but archived, because they would open to nothing.

## Everything it changes can be put back

Each file it creates is listed; the original of each file it overwrites or removes is backed up first. `--undo` removes what it created and restores every original, timestamps included. It never touches a transcript, and it never deletes anything you did not already delete yourself.

## Your sidebar groups, too

The conversation list is only half of what the sidebar shows. The groups you made — their names, which conversations sit in each, their order, which ones are collapsed — are stored separately, per account, in the app's own browser storage. `--sidebar-from=<account>` copies one account's layout to every other account, dropping any grouped conversation that account does not hold.

This one needs the app fully quit (Cmd-Q), because the app keeps the layout in memory and would write over the change; the script checks and refuses otherwise, so run it from Terminal rather than from inside the app. It copies the whole storage directory first, checks the new value after writing and puts the copy back if anything is off, and `--undo` restores it. To take back only the latest layout change and keep your aligned conversation lists, use `--undo-sidebar` instead. It only reaches the desktop app's sidebar on this machine: artifacts and anything claude.ai keeps on its servers per account stay where they are.

## The restart

A run does not appear until the desktop app restarts. The app reads this index when it starts and does not look at the directory again while it is running.

That matters more than it sounds, because restarting interrupts whatever conversations are still running. The run tells you to restart rather than doing anything about it, and checking what is live first is worth the ten seconds.
