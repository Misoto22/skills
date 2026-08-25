# Forge metadata

The About text and the topics live on the forge, not in the repository. Nothing about them appears in a diff, no review sees them, and no `git revert` puts one back. Print the exact values and get a yes before sending either.

Read what is set before writing. Both fields usually already hold something, and replacing a description someone wrote by hand is a worse outcome than leaving an empty one empty.

---

## Description

One line, on the repository's page and in every search result, list, and directory card that names it.

- **It is the sentence** — the same text as the README's centred line and the package manifest's `description`. Not a paraphrase.
- **Under 120 characters.** GitHub's hard limit is 350, but a repository list truncates far earlier, and truncation lands mid-word.
- **Do not open with the repository's name.** It is rendered directly above.
- **No trailing period on a fragment**, no marketing adjective, no emoji as the first character.
- **A URL belongs in the website field beside it**, not inside the sentence. Setting that field is what makes the link render as a link.

> `Self-hosted task tracker — Rust API, Postgres, htmx front end`
>
> not `🚀 SuperTask is a blazing-fast, modern solution for managing your team's work!`

### GitHub

```bash
gh repo view <owner>/<repo> --json description,homepageUrl,repositoryTopics
gh repo edit <owner>/<repo> --description "<the sentence>" --homepage "<url>"
```

Or through the API directly, which is what to reach for when the CLI is absent:

```bash
gh api repos/<owner>/<repo> --method PATCH \
  --field description="<the sentence>" \
  --field homepage="<url>"
```

### GitLab

The project description is a `PUT` on the project. `glab api` is the transport that is always present; check `glab repo --help` on the installed version for a shorthand before assuming there is none.

```bash
glab api projects/<url-encoded-path> --method PUT --field description="<the sentence>"
```

The path is URL-encoded — `group%2Fsubgroup%2Fproject` — or the numeric project id.

GitLab also renders the repository's own `README.md` on the project page, so the description carries less weight there than on GitHub. It still shows in search and in group listings.

---

## Topics

Topics are how someone who does not know the repository exists finds it. That is the only test a candidate has to pass: would a stranger type this word while looking for something like this?

### What qualifies

- **Technologies a user would search for** — `rust`, `postgresql`, `next-js`, `claude-code`.
- **The domain** — `task-management`, `static-site-generator`, `astrology`.
- **The kind of artefact** — `cli`, `library`, `plugin`, `self-hosted`.
- **The directory's own convention**, where the repository publishes into an ecosystem that has one. Read what comparable repositories in it use rather than inventing a term.

### What does not

- **The repository's own name.** It already matches on name.
- **Judgements about the code** — `well-architected`, `production-ready`, `awesome`.
- **Terms with no audience** — `personal-project`, `wip`, `my-config`.
- **Synonym stuffing** — `js`, `javascript`, `java-script` is one topic, chosen once.
- **Anything that stopped being true.** Read the existing set and drop what the repository no longer does; a stale topic sends people to the wrong place, which is worse than sending nobody.

### Limits

| | GitHub |
|---|---|
| Topics per repository | 20 |
| Characters per topic | 50 |
| Allowed characters | lowercase letters, digits, hyphens |
| Must start with | a letter or a digit |

GitHub normalises whatever you send — uppercase is lowercased, spaces and underscores become hyphens. Write them normalised so the set you send is the set you get back.

Eight to twelve is usually the honest count. A repository claiming twenty topics is claiming twenty audiences.

### GitHub

Adding and removing, leaving the rest alone:

```bash
gh repo edit <owner>/<repo> --add-topic rust,cli,self-hosted
gh repo edit <owner>/<repo> --remove-topic python2
```

Replacing the whole set — every topic not listed is dropped, so read the current set first:

```bash
gh api repos/<owner>/<repo>/topics --method PUT \
  --field 'names[]=rust' --field 'names[]=cli' --field 'names[]=self-hosted'
```

### GitLab

GitLab calls them topics too, on the same `PUT`, and it also replaces the whole set:

```bash
glab api projects/<url-encoded-path> --method PUT \
  --field 'topics[]=rust' --field 'topics[]=cli'
```

---

## When there is no forge access

A repository with no configured remote, a host without the CLI, an account without push rights on that repository, or an authentication error — any of these ends the pass. It does not end the polish.

Report the two passes as blocked, and hand over the exact values and the exact command, ready to paste:

> **Blocked — forge metadata.** `gh` is not authenticated for `acme/supertask`.
>
> ```bash
> gh repo edit acme/supertask --description "Self-hosted task tracker — Rust API, Postgres, htmx front end"
> gh repo edit acme/supertask --add-topic rust,postgresql,htmx,task-management,self-hosted,cli
> ```

Never report a field as set on the strength of having composed a value for it. These two passes are the only ones in this skill whose result cannot be seen in the working tree, which is exactly why they are the ones to state plainly.
