#!/usr/bin/env python3
"""Scaffold a skill, and register it everywhere the validator will look.

Adding a skill by hand means editing six places — PUBLISHED in the validator,
marketplace.json if the plugin is new, the plugin manifest, both READMEs, the
install workflow's --expect list, and .version-bump.json. The validator catches
a missed one, but catching is not the same as doing.

  python3 scripts/new-skill.py writing outline    Add a skill to an existing plugin
  python3 scripts/new-skill.py notes capture      Create the plugin too, if it is new

Writes a SKILL.md the validator accepts and a description that will not trigger
on anything. Both are placeholders: the description is the only field that
decides whether a skill ever fires, so rewrite it before committing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
KEBAB = re.compile(r"^[a-z][a-z0-9-]*$")

SKILL_TEMPLATE = """---
name: {skill}
description: PLACEHOLDER, rewrite before committing — say in concrete terms when to use this skill, name the artefacts and phrasings that should trigger it, and end with what it is not for. One line; the frontmatter parser does not fold. Triggering depends entirely on this field.
license: MIT
metadata:
  version: "{version}"
---

# {title}

One sentence stating the job this skill does.

## PLACEHOLDER

Replace this with the rules an agent has to follow. Keep them concrete and
executable — specific instructions, banned constructions, worked before-and-after
pairs. Abstract exhortations belong nowhere.

Every path named here must resolve from this directory on every installer. Paths
that climb out of the skill, and environment variables only one agent expands, are
both rejected by the validator — see AGENTS.md.
"""

AGENT_TEMPLATE = """interface:
  display_name: "{title}"
  short_description: "PLACEHOLDER — one line, under 60 characters"
  default_prompt: "Use ${skill} to PLACEHOLDER."
policy:
  allow_implicit_invocation: true
"""

PLUGIN_README_TEMPLATE = """# Published skills

Only release-ready, recursively discoverable skills belong in this directory.

- [{skill}]({skill}/SKILL.md) — PLACEHOLDER, one line.

This plugin has no `shared/` directory yet. Add one when a second skill needs the
same concrete rules; a single skill does not need the indirection.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin", help="plugin name, kebab-case; created if it does not exist")
    parser.add_argument("skill", help="skill directory name, kebab-case")
    args = parser.parse_args()

    for label, value in (("plugin", args.plugin), ("skill", args.skill)):
        if not KEBAB.match(value):
            print(
                f"error: {label} name {value!r} must be kebab-case — lowercase letters,"
                " digits and hyphens. Claude Code is lenient here; the claude.ai"
                " marketplace sync is not.",
                file=sys.stderr,
            )
            return 1

    skill_dir = PLUGINS_ROOT / args.plugin / "skills" / args.skill
    if skill_dir.exists():
        print(f"error: {skill_dir.relative_to(ROOT)} already exists", file=sys.stderr)
        return 1

    version = _current_version()
    title = args.skill.replace("-", " ").title()
    created: list[str] = []

    plugin_manifest = PLUGINS_ROOT / args.plugin / ".claude-plugin" / "plugin.json"
    new_plugin = not plugin_manifest.is_file()

    (skill_dir / "agents").mkdir(parents=True)
    _write(
        skill_dir / "SKILL.md",
        SKILL_TEMPLATE.format(skill=args.skill, title=title, version=version),
        created,
    )
    _write(
        skill_dir / "agents" / "openai.yaml",
        AGENT_TEMPLATE.format(skill=args.skill, title=title),
        created,
    )

    if new_plugin:
        plugin_manifest.parent.mkdir(parents=True, exist_ok=True)
        _write(
            plugin_manifest,
            json.dumps(
                {
                    "name": args.plugin,
                    "version": version,
                    "description": f"PLACEHOLDER — what {args.plugin} skills are for.",
                    "author": {"name": "skills contributors"},
                    "license": "MIT",
                    "skills": [f"./skills/{args.skill}"],
                },
                indent=2,
            )
            + "\n",
            created,
        )
        _write(
            skill_dir.parent / "README.md",
            PLUGIN_README_TEMPLATE.format(skill=args.skill),
            created,
        )
        _register_marketplace(args.plugin, created)
    else:
        _add_to_plugin_manifest(plugin_manifest, args.skill, created)
        _add_to_plugin_readme(skill_dir.parent / "README.md", args.skill, created)

    _register_published(args.plugin, args.skill, created)
    _register_workflow(args.plugin, args.skill, new_plugin, created)
    _register_root_readme(args.plugin, args.skill, created)
    _register_version_bump(args.plugin, args.skill, new_plugin, created)

    for path in created:
        print(f"  {path}")
    print(f"\nScaffolded {args.plugin}/{args.skill} → /{args.plugin}:{args.skill}")
    print("Still yours to do, in this order:")
    print(f"  1. Rewrite the description in plugins/{args.plugin}/skills/{args.skill}/SKILL.md")
    print("     — it is the only field that decides whether the skill ever fires.")
    print("  2. Write the body, and replace the README and plugin-registry placeholders.")
    print("  3. python3 scripts/validate-repository.py")
    return 0


def _current_version() -> str:
    text = (ROOT / "scripts" / "validate-repository.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION = "([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("error: could not read VERSION from validate-repository.py")
    return match.group(1)


def _write(path: Path, content: str, created: list[str]) -> None:
    path.write_text(content, encoding="utf-8")
    created.append(str(path.relative_to(ROOT)))


def _edit(path: Path, old: str, new: str, created: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"error: could not find the insertion point in {path.relative_to(ROOT)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    created.append(f"{path.relative_to(ROOT)} (updated)")


def _add_to_plugin_manifest(path: Path, skill: str, created: list[str]) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entry = f"./skills/{skill}"
    if entry in manifest["skills"]:
        return
    manifest["skills"] = sorted([*manifest["skills"], entry])
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    created.append(f"{path.relative_to(ROOT)} (updated)")


def _add_to_plugin_readme(path: Path, skill: str, created: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    last = max(index for index, line in enumerate(lines) if line.startswith("- ["))
    lines.insert(last + 1, f"- [{skill}]({skill}/SKILL.md) — PLACEHOLDER, one line.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    created.append(f"{path.relative_to(ROOT)} (updated)")


def _register_marketplace(plugin: str, created: list[str]) -> None:
    path = ROOT / ".claude-plugin" / "marketplace.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if any(entry["name"] == plugin for entry in manifest["plugins"]):
        return
    manifest["plugins"].append({"name": plugin, "source": f"./plugins/{plugin}"})
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    created.append(f"{path.relative_to(ROOT)} (updated)")


def _register_published(plugin: str, skill: str, created: list[str]) -> None:
    path = ROOT / "scripts" / "validate-repository.py"
    text = path.read_text(encoding="utf-8")
    match = re.search(rf'^    "{plugin}": \[([^\]]*)\],$', text, re.MULTILINE)
    if match:
        names = sorted({*re.findall(r'"([^"]+)"', match.group(1)), skill})
        listed = ", ".join(f'"{name}"' for name in names)
        _edit(path, match.group(0), f'    "{plugin}": [{listed}],', created)
        return
    _edit(path, "PUBLISHED = {\n", f'PUBLISHED = {{\n    "{plugin}": ["{skill}"],\n', created)


def _register_root_readme(plugin: str, skill: str, created: list[str]) -> None:
    """Add the bullet the validator looks for, with the source link it checks."""

    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    last = max(index for index, line in enumerate(lines) if line.startswith("- **["))
    bullet = (
        f"- **[{skill}](plugins/{plugin}/skills/{skill}/SKILL.md)**"
        f" (`/{plugin}:{skill}`) — PLACEHOLDER, one line."
    )
    lines.insert(last + 1, bullet)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    created.append(f"{path.relative_to(ROOT)} (updated)")


def _register_version_bump(plugin: str, skill: str, new_plugin: bool, created: list[str]) -> None:
    """A new SKILL.md carries a version, so the bumper has to know about it."""

    path = ROOT / ".version-bump.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    skill_file = f"plugins/{plugin}/skills/{skill}/SKILL.md"
    if skill_file not in config["text"]:
        config["text"].insert(0, skill_file)
    manifest = f"plugins/{plugin}/.claude-plugin/plugin.json"
    if new_plugin and all(entry["path"] != manifest for entry in config["json"]):
        config["json"].append({"path": manifest, "field": "version"})
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    created.append(f"{path.relative_to(ROOT)} (updated)")


def _register_workflow(plugin: str, skill: str, new_plugin: bool, created: list[str]) -> None:
    """CI installs each plugin by name, so a new plugin needs its own install line."""

    path = ROOT / ".github" / "workflows" / "install.yml"
    text = path.read_text(encoding="utf-8")
    updated = text.replace("--expect tempering", f"--expect tempering --expect {skill}")
    if updated == text:
        raise SystemExit("error: could not find the --expect list in install.yml")

    if new_plugin:
        for line, addition in (
            (
                "          claude plugin install writing@misoto22\n",
                f"          claude plugin install {plugin}@misoto22\n",
            ),
            (
                "          codex plugin add writing@misoto22\n",
                f"          codex plugin add {plugin}@misoto22\n",
            ),
        ):
            if line not in updated:
                raise SystemExit(f"error: could not find the install line to extend in {path.name}")
            updated = updated.replace(line, line + addition, 1)
    path.write_text(updated, encoding="utf-8")
    created.append(f"{path.relative_to(ROOT)} (updated)")


if __name__ == "__main__":
    raise SystemExit(main())
