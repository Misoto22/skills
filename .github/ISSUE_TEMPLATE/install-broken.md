---
name: A skill installed but does not work
about: Missing files, dangling references, or a skill the agent cannot see
labels: install
---

**Route** — Claude Code plugin · Codex plugin · `npx skills` · uploaded `.skill`

**Agent and version**

**What the installed tree looks like**

```
$ python3 scripts/verify-install.py <path to the installed skill>
```

<!--
Point it at the directory the installer produced — a plugin cache, an
~/.agents/skills copy, an unpacked .skill. That is the artefact the agent reads,
and it is where a missing shared/ file shows up. Paste the output.
-->

**What you expected instead**
