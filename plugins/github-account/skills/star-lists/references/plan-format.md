# Plan format

A plan is the desired state of an account's star lists. `export` writes one that matches the live account; `apply` makes the account match whatever plan it is given. Backups use the same format.

```json
{
  "format": "github-star-lists/v1",
  "account": "octocat",
  "lists": [
    {"key": "ai-agents", "id": "UL_kwDOExampleList01", "name": "AI · Agents", "description": "Coding agents and chat apps", "private": false},
    {"key": "fonts", "name": "Design · Fonts", "description": "Typefaces", "private": false}
  ],
  "assignments": {
    "openhands/openhands": ["ai-agents"],
    "vercel/geist-font": ["fonts"]
  },
  "repos": {
    "openhands/openhands": {"description": "AI-driven development", "language": "Python", "topics": ["agent"]}
  }
}
```

| Field | Meaning |
|---|---|
| `format` | Always `github-star-lists/v1`. Anything else is refused. |
| `account` | The login the plan was exported from. `check` refuses to apply it while gh is signed in as someone else. |
| `lists[].key` | Lowercase letters, digits and hyphens, unique. Used only by `assignments`. |
| `lists[].id` | The existing list this entry keeps. Omit it to create a list. An id the account no longer has (a list deleted after a backup) is recreated. |
| `lists[].name` | Required, unique ignoring case, at most 32 characters, English. |
| `lists[].description` | Optional, at most 160 characters, English. |
| `lists[].private` | Optional, `false` by default. |
| `assignments` | Every starred repository, `owner/name`, mapped to the keys of its lists. An empty array means no list. |
| `repos` | Written by `export` for reading only. `apply` ignores it. |

Rules `check` enforces:

- At most 32 lists.
- Every key in `assignments` names a list in `lists`.
- Every repository in `assignments` is starred by the signed-in account.
- Every starred repository has at least one list, unless `--allow-unassigned` is passed.
- No two lists claim the same `id`.
- List names and descriptions contain no Han, kana, Hangul, CJK punctuation or fullwidth characters.

A live list whose `id` appears nowhere in the plan is deleted. Its repositories stay starred.
