#!/usr/bin/env python3
"""Scaffold a skill, and register it everywhere the validator will look.

Adding a skill by hand means editing seven places — PUBLISHED in the validator,
marketplace.json if the plugin is new, both plugin manifests, both READMEs,
.version-bump.json, and skills.sh.json. The validator catches a missed one, but
catching is not the same as doing.

Two manifests, because two families of client read one: Claude Code reads
.claude-plugin/plugin.json, and everything implementing Agent Plugins reads
plugin.json at the plugin root.

The install workflow is not one of them. It derives both the plugin list and the
expected skill names from the tree, so nothing there is written down twice.

  python3 scripts/new-skill.py writing outline    Add a skill to an existing plugin
  python3 scripts/new-skill.py notes capture      Create the plugin too, if it is new

Writes a SKILL.md that satisfies every registry check and a description that
satisfies none. That is deliberate: the description is the only field deciding
whether a skill ever fires, so the validator fails on the placeholder until it
is rewritten. Everything mechanical is done; the one judgement call is not.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
KEBAB = re.compile(r"^[a-z][a-z0-9-]*$")

SKILL_TEMPLATE = """---
name: {skill}
description: PLACEHOLDER, rewrite before committing — say in concrete terms when to use this skill, name the artefacts and phrasings that should trigger it, and end with what it is not for. One line; the frontmatter parser does not fold. Triggering depends entirely on this field.
license: {license_name}
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
    parser.add_argument(
        "--category",
        default="development",
        help="category for a new plugin's marketplace entry; ignored for an existing one",
    )
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
    license_name = "MIT" if new_plugin else json.loads(plugin_manifest.read_text(encoding="utf-8"))["license"]

    (skill_dir / "agents").mkdir(parents=True)
    _write(
        skill_dir / "SKILL.md",
        SKILL_TEMPLATE.format(
            skill=args.skill,
            title=title,
            version=version,
            license_name=license_name,
        ),
        created,
    )
    _write(
        skill_dir / "agents" / "openai.yaml",
        AGENT_TEMPLATE.format(skill=args.skill, title=title),
        created,
    )

    if new_plugin:
        description = f"PLACEHOLDER — what {args.plugin} skills are for."
        plugin_manifest.parent.mkdir(parents=True, exist_ok=True)
        _write(
            plugin_manifest,
            json.dumps(
                {
                    "name": args.plugin,
                    "version": version,
                    "description": description,
                    "author": {"name": "skills contributors"},
                    "license": "MIT",
                    "skills": [f"./skills/{args.skill}"],
                },
                indent=2,
            )
            + "\n",
            created,
        )
        _write_agent_plugin(args.plugin, version, description, created)
        _write(
            skill_dir.parent / "README.md",
            PLUGIN_README_TEMPLATE.format(skill=args.skill),
            created,
        )
    else:
        _add_to_plugin_manifest(plugin_manifest, args.skill, created)
        _add_to_plugin_readme(skill_dir.parent / "README.md", args.skill, created)

    _register_marketplace(args.plugin, args.skill, args.category, created)
    _register_bundle(args.plugin, created)
    _register_published(args.plugin, args.skill, created)
    _register_root_readme(args.plugin, args.skill, created)
    _register_version_bump(args.plugin, args.skill, new_plugin, created)
    _register_skills_sh(args.plugin, args.skill, created)
    _register_translations(args.plugin, args.skill, new_plugin, created)
    # Last two, in this order: both read the tree the steps above changed, and
    # the registry reads skills.sh.json and i18n/ among it.
    _restate_counts(created)
    _rebuild_registry(created)

    for path in created:
        print(f"  {path}")
    print(f"\nScaffolded {args.plugin}/{args.skill} → /{args.plugin}:{args.skill}")
    print("Still yours to do, in this order:")
    print(f"  1. Rewrite the description in plugins/{args.plugin}/skills/{args.skill}/SKILL.md")
    print("     — it is the only field that decides whether the skill ever fires,")
    print("       and the validator fails on the placeholder until you do.")
    print("  2. Write the body, and replace the README and plugin-registry placeholders.")
    print(f"     Including i18n/*.json — {args.skill}'s entry is scaffolded there too, and")
    print("     build-registry.py refuses a scaffolded translation the same way.")
    if new_plugin:
        print(f"     Including `keywords` in plugins/{args.plugin}/plugin.json — the terms a")
        print("     plugin directory searches on, and the only field nothing here reads.")
    print(f"  3. Write evals/{args.skill}/evals.json — at least three prompts it must fire")
    print("     on and two it must stay out of. run-evals.py --check fails until it exists.")
    print("  4. python3 scripts/validate-repository.py")
    return 0


def _load_validator():
    """Load validate-repository.py, which owns the registries this script edits.

    Imported by path because the filename is hyphenated. Executing it defines
    the registries and their helpers and runs nothing; `main()` is guarded.
    """

    path = ROOT / "scripts" / "validate-repository.py"
    spec = importlib.util.spec_from_file_location("validate_repository", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"error: cannot load {path.relative_to(ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _restate_counts(created: list[str]) -> None:
    """The READMEs state a published count, and the tree just changed under it."""

    for name in _load_validator().restate_counts():
        created.append(f"{name} (count restated)")


def _marketplace_name() -> str:
    """Read the install suffix from the manifest that has to declare it anyway.

    `<plugin>@<marketplace>` is what a user types and what the bundle depends
    on. Writing the name here as well would make a rename something half the
    repository follows.
    """

    manifest = ROOT / ".claude-plugin" / "marketplace.json"
    return str(json.loads(manifest.read_text(encoding="utf-8"))["name"])


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


def _write_agent_plugin(plugin: str, version: str, description: str, created: list[str]) -> None:
    """The manifest every client that is not Claude Code reads, at the plugin root.

    Its $schema and repository are copied from a sibling rather than written here,
    for one reason: the schema URL carries a semver, this repository's own version
    is moved by a plain string replace, and a release reaching that same number
    would rewrite one with the other. The value lives only in files the bumper
    edits by field, where a version inside a URL cannot be mistaken for the field.
    """

    sibling = next(
        (path for path in sorted(PLUGINS_ROOT.glob("*/plugin.json")) if path.parent.name != plugin),
        None,
    )
    if sibling is None:
        raise SystemExit(
            "error: no existing plugins/*/plugin.json to copy the Agent Plugins schema from."
            " Write the first one by hand, from https://agent-plugins.org/specification."
        )
    template = json.loads(sibling.read_text(encoding="utf-8"))
    _write(
        PLUGINS_ROOT / plugin / "plugin.json",
        json.dumps(
            {
                "$schema": template["$schema"],
                "name": plugin,
                "version": version,
                "description": description,
                "author": {"name": "skills contributors"},
                "license": "MIT",
                # Three placeholders rather than none: the validator floors the
                # count, so an empty list would fail with a rule the author has
                # no reason to have read yet. These say what to replace.
                "keywords": [f"{plugin}-term-1", f"{plugin}-term-2", f"{plugin}-term-3"],
                "homepage": template["homepage"],
                "repository": template["repository"],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        created,
    )


def _add_to_plugin_readme(path: Path, skill: str, created: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    last = max(index for index, line in enumerate(lines) if line.startswith("- ["))
    lines.insert(last + 1, f"- [{skill}]({skill}/SKILL.md) — PLACEHOLDER, one line.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    created.append(f"{path.relative_to(ROOT)} (updated)")


def _register_marketplace(plugin: str, skill: str, category: str, created: list[str]) -> None:
    path = ROOT / ".claude-plugin" / "marketplace.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entry = f"./skills/{skill}"
    registered = next((item for item in manifest["plugins"] if item["name"] == plugin), None)
    if registered is None:
        # Full path from the repository root: metadata carries no pluginRoot,
        # because the two installers disagree on what it means.
        manifest["plugins"].append(
            {
                "name": plugin,
                "category": category,
                "source": f"./plugins/{plugin}",
                "skills": [entry],
            }
        )
    elif entry in registered["skills"]:
        return
    else:
        registered["skills"] = sorted([*registered["skills"], entry])
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    created.append(f"{path.relative_to(ROOT)} (updated)")


def _register_bundle(plugin: str, created: list[str]) -> None:
    """A new plugin joins the one-command install, or that command stops being one."""

    path = ROOT / "bundle" / ".claude-plugin" / "plugin.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entry = f"{plugin}@{_marketplace_name()}"
    if entry in manifest["dependencies"]:
        return
    manifest["dependencies"] = sorted([*manifest["dependencies"], entry])
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
    """Add the bullet the validator looks for, with the source link it checks.

    Every root README, translations included. The validator holds each of them to
    the same registry, so a translation the scaffold skipped would fail the build
    of whoever adds the next skill rather than of whoever left it behind.
    """

    bullet = (
        f"- **[{skill}](plugins/{plugin}/skills/{skill}/SKILL.md)**"
        f" (`/{plugin}:{skill}`) — PLACEHOLDER, one line."
    )
    for path in sorted(ROOT.glob("README*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        last = max(index for index, line in enumerate(lines) if line.startswith("- **["))
        lines.insert(last + 1, bullet)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        created.append(f"{path.relative_to(ROOT)} (updated)")


def _register_skills_sh(plugin: str, skill: str, created: list[str]) -> None:
    """skills.sh renders this file, so an unlisted skill is only visible to users."""

    path = ROOT / "skills.sh.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    # The skills CLI title-cases a plugin name for its own group headings, and the
    # directory page renders this string verbatim, so it carries the same casing.
    title = plugin.replace("-", " ").title()
    group = next((g for g in config["groupings"] if g["title"] == title), None)
    if group is None:
        group = {
            "title": title,
            "description": f"PLACEHOLDER — what {plugin} skills are for, in one sentence.",
            "skills": [],
        }
        config["groupings"].append(group)
    if skill not in group["skills"]:
        group["skills"].append(skill)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    created.append(f"{path.relative_to(ROOT)} (updated)")


def _register_translations(plugin: str, skill: str, new_plugin: bool, created: list[str]) -> None:
    """Add a scaffolded entry per locale, which the registry build then rejects.

    Same bargain as the SKILL.md description: everything mechanical is done, and
    the one part needing a person is left visibly undone rather than quietly
    shipped. Without an entry at all the build fails with "no zh entry", which
    reads like a bug in the scaffold instead of work still to do.
    """

    for path in sorted((ROOT / "i18n").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        locale = path.stem
        if new_plugin:
            data.setdefault("groups", {})[plugin] = {
                "title": f"PLACEHOLDER — {plugin} in {locale}",
                "description": f"PLACEHOLDER — what {plugin} skills are for, in {locale}.",
                "summary": f"PLACEHOLDER — one line about {plugin}, in {locale}.",
            }
        # Appended, not sorted into place: these files read in catalogue order —
        # the order the groups appear on the page — and re-sorting them
        # alphabetically would rewrite the whole file for every new skill, and
        # leave the retirement unable to put it back byte for byte.
        data.setdefault("skills", {})[skill] = {
            "description": f"PLACEHOLDER — what {skill} does and when to use it, in {locale}.",
            "overview": f"PLACEHOLDER — a paragraph introducing {skill} to a {locale} reader.",
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        created.append(f"{path.relative_to(ROOT)} (updated)")


def _rebuild_registry(created: list[str]) -> None:
    """The published catalogue is generated, so a new skill has to regenerate it.

    Not `check=True`: the entries written a moment ago are scaffolded, and the
    build rejects a scaffolded translation exactly as the validator rejects a
    scaffolded description. That refusal is the point, so it is reported as work
    outstanding rather than raised as a failure of the scaffold.
    """

    built = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build-registry.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    created.append(
        "registry.json (rebuilt)"
        if built.returncode == 0
        else "registry.json (NOT rebuilt — write the translations first)"
    )


def _register_version_bump(plugin: str, skill: str, new_plugin: bool, created: list[str]) -> None:
    """A new SKILL.md carries a version, so the bumper has to know about it."""

    path = ROOT / ".version-bump.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    skill_file = f"plugins/{plugin}/skills/{skill}/SKILL.md"
    if skill_file not in config["text"]:
        config["text"].insert(0, skill_file)
    # Both manifests: Claude Code's, and the Agent Plugins one beside it. A
    # version declared in one and left behind in the other is drift the validator
    # reports but nothing repairs.
    for manifest in (
        f"plugins/{plugin}/.claude-plugin/plugin.json",
        f"plugins/{plugin}/plugin.json",
    ):
        if new_plugin and all(entry["path"] != manifest for entry in config["json"]):
            config["json"].append({"path": manifest, "field": "version"})
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    created.append(f"{path.relative_to(ROOT)} (updated)")


if __name__ == "__main__":
    raise SystemExit(main())
