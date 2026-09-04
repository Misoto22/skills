# Installing the session-naming hook by hand

Only for a skill installed on its own — `npx skills add`, skills.sh, or a client that copies a skill directory rather than a plugin. A `dev` plugin install registers the hook itself; installing it again here runs it twice.

Copy the hook next to the user's other Claude Code scripts:

```bash
mkdir -p "$HOME/.claude/scripts"
cp assets/session-naming-hook.py "$HOME/.claude/scripts/session-naming-hook.py"
chmod +x "$HOME/.claude/scripts/session-naming-hook.py"
```

`$HOME/.claude` is the default configuration directory. Where the user has moved it, substitute the real one — the hook reads the same override itself when deciding where to keep its markers, so the two stay together.

Then add it to `settings.json` in that directory, under `hooks.UserPromptSubmit`, as a `command` entry running that path. Read the existing file and merge — a settings file rewritten from scratch loses whatever else the user had configured, which is the one failure here that costs more than a bad title.

The hook names in English unless told otherwise. To keep a machine naming in Chinese, set `SESSION_TITLE_LANG` on the hook's own command rather than in a shell profile — a setting that lives in the settings entry is one the next reader of that file can see:

```bash
SESSION_TITLE_LANG=zh python3 "$HOME/.claude/scripts/session-naming-hook.py"
```

Verify it before trusting it, because a hook that throws is a hook that breaks every prompt:

```bash
printf '{"session_id":"verify-install"}' | python3 "$HOME/.claude/scripts/session-naming-hook.py"
```

That must print one JSON object containing the scheme — `MMDD｜TYPE｜subject`, or `MMDD｜类型｜主题` when the entry sets `SESSION_TITLE_LANG=zh`. Remove the marker it just created (`.session-naming-markers/verify-install` under the config directory) so a real session is not counted as already reminded.
