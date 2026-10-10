`star-prune` is for the stars that have quietly stopped being useful: repositories their owners archived, ones whose README now says "deprecated, use X instead", a few GitHub disabled outright. They sit between the stars you still return to and make the whole list harder to use. This finds them, says exactly why each one was flagged, and unstars only the ones you agree to.

## What it flags, and what it leaves alone

```
Wrote prune.json: 21 of 156 starred repositories flagged.
  archived     3  haha114514/No_Telstra_IPv6, meta-llama/codellama, siddharthvaddem/openscreen
  dormant     18  apachecn/awesome-cs-courses-zh, cits4407/assignment1, ijpq/cs267 ...
Proposed: unstar 3, keep 18.
```

Archived, disabled and deprecated repositories are proposed for unstarring; "deprecated" needs the repository's own description or topics to say so, and the report quotes the words it found. Repositories with no push in two years are listed but kept by default, because a finished library and an abandoned one look the same from the outside, and course notes or a roadmap you keep on purpose should not be swept up. Your own repositories are never flagged.

You decide each one. Say "unstar the archived ones and keep the rest" and that is what happens; a repository you want out of sight without unstarring belongs in an Archive list, which `star-lists` handles.

## How it keeps you safe

Nothing is unstarred until you have seen the list and said yes. Before the first unstar it saves a backup with every repository and the lists it was in, then reads your stars back to confirm each one is gone. `restore` stars them again and puts each back into its lists. GitHub does not keep the original star date, so restored stars sort as new; that is the one thing a restore cannot bring back.

Like `star-lists`, it runs on a machine with nothing installed: `run.sh doctor --install` fetches the GitHub CLI and uv from their releases, checks each against its published SHA-256, and installs them in your home directory without `sudo`.

## What it will not do

It does not sort stars into lists, star new repositories, archive or delete repositories you own, or touch notifications. A renamed repository is not flagged, because GitHub follows renames for you. Everything it writes is in English, whatever language you ask in.
