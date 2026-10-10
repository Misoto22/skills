`star-lists` is for the moment you open GitHub's **Starred** dropdown and the lists there no longer make sense: names in three different styles, a typo nobody fixed, five lists with one repository each, and half your stars in no list at all. It reads every repository you have starred, has your agent design a set of lists that fits what is actually there, and files each star into the right one, or into two when it genuinely belongs to both.

## What you see before anything changes

Nothing is written until you have seen the change and said yes. The agent shows you a diff like this:

```
Lists: 1 to create, 20 to update, 0 to delete. Repositories: 155 to move.
  update  Tools - Cluade Code: rename to 'AI · Claude Code'
  update  Study - CI/CD: rename to 'Study · Interview & Algorithms'
  create  AI · Design Skills
  move    obra/superpowers: Tools - Cluade Code -> AI · Claude Code
  move    vercel/geist-font: Fonts -> Design · Fonts & Icons
  ...
```

If you would rather click than read, it writes a review page: every starred repository with every list as a toggle, so one repository can sit in several lists. Save the edited plan from the page and the agent applies that instead.

## How it keeps you safe

Every change goes through one plan file. `check` refuses a plan that leaves a star in no list, names a repository you have not starred, exceeds GitHub's limits of 32 lists, 32-character names and 160-character descriptions, or puts non-English text into a list name. `apply` saves a backup of your current lists before its first write and reads your account back afterwards to confirm it matches. A backup is itself a plan, so undoing a reorganization is applying the backup. Deleting a list never unstars anything.

It runs on a machine with nothing installed. `run.sh doctor` reports what is missing, and `doctor --install` downloads the GitHub CLI and uv from their GitHub releases, checks each download against its published SHA-256, and puts them in your home directory without `sudo`. You sign in through gh's browser code flow, so no password or token passes through the conversation.

## What it will not do

It does not star or unstar repositories, organize repositories you own, touch GitHub Projects, or sort browser bookmarks. Everything it generates (list names, descriptions, files) is in English, whatever language you ask in. GitHub offers Lists only through its GraphQL API and still calls the feature a preview, so a change on GitHub's side can break it; when that happens, the error names the call that failed.
