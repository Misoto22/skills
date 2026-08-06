#!/usr/bin/env python3
"""Retire a skill, and unregister it everywhere new-skill.py registered it.

Adding a skill is a scripted seven-file edit; removing one was seven by hand,
with the validator reporting them one at a time. That asymmetry is why nothing
here has ever been retired: the cost of taking a skill out was higher than the
cost of leaving it in, which is how a catalogue fills with things nobody uses.

  python3 scripts/remove-skill.py writing outline    Move it under deprecated/
  python3 scripts/remove-skill.py writing outline --delete

The default keeps the material. A retired skill moves to
`deprecated/<plugin>/<skill>/` with its evaluation cases beside it, so what it
said and what it was tested against survive the decision to stop shipping it.
Emptying a plugin retires the plugin too — its manifest, its marketplace entry,
and its group on the directory page.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
EVALS_ROOT = ROOT / "evals"
DEPRECATED_ROOT = ROOT / "deprecated"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin")
    parser.add_argument("skill")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="remove the files instead of moving them under deprecated/",
    )
    args = parser.parse_args()

    skill_dir = PLUGINS_ROOT / args.plugin / "skills" / args.skill
    if not (skill_dir / "SKILL.md").is_file():
        print(f"error: {skill_dir.relative_to(ROOT)} is not a published skill", file=sys.stderr)
        return 1

    plugin_root = PLUGINS_ROOT / args.plugin
    remaining = sorted(
        path.parent.name for path in plugin_root.glob("skills/*/SKILL.md") if path.parent != skill_dir
    )
    retires_plugin = not remaining
    touched: list[str] = []

    _retire_files(args.plugin, args.skill, skill_dir, retires_plugin, args.delete, touched)
    _unregister_published(args.plugin, args.skill, retires_plugin, touched)
    _unregister_root_readme(args.plugin, args.skill, touched)
    _unregister_version_bump(args.plugin, args.skill, retires_plugin, touched)
    _unregister_skills_sh(args.plugin, args.skill, touched)
    _drop_dangling_hand_offs(args.skill, touched)
    if retires_plugin:
        _unregister_marketplace(args.plugin, touched)
    else:
        _unregister_plugin_manifest(plugin_root, args.skill, touched)
        _unregister_plugin_readme(plugin_root / "skills" / "README.md", args.skill, touched)

    for entry in touched:
        print(f"  {entry}")
    verb = "Deleted" if args.delete else "Retired"
    print(f"\n{verb} {args.plugin}/{args.skill}" + (" and its plugin" if retires_plugin else ""))
    print("Next: python3 scripts/validate-repository.py, then note it in CHANGELOG.md.")
    return 0


def _retire_files(
    plugin: str,
    skill: str,
    skill_dir: Path,
    retires_plugin: bool,
    delete: bool,
    touched: list[str],
) -> None:
    """Move or remove the skill tree, the evaluation cases, and an emptied plugin."""

    evals_dir = EVALS_ROOT / skill
    if delete:
        shutil.rmtree(skill_dir)
        touched.append(f"{skill_dir.relative_to(ROOT)} (deleted)")
        if evals_dir.is_dir():
            shutil.rmtree(evals_dir)
            touched.append(f"{evals_dir.relative_to(ROOT)} (deleted)")
    else:
        destination = DEPRECATED_ROOT / plugin / skill
        if destination.exists():
            raise SystemExit(f"error: {destination.relative_to(ROOT)} already exists")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(skill_dir), str(destination))
        touched.append(f"{destination.relative_to(ROOT)} (moved)")
        if evals_dir.is_dir():
            shutil.move(str(evals_dir), str(destination / "evals"))
            touched.append(f"{(destination / 'evals').relative_to(ROOT)} (moved)")

    if retires_plugin:
        plugin_root = PLUGINS_ROOT / plugin
        # The shared/ directory and the plugin manifest go with the last skill;
        # a plugin that publishes nothing is not a plugin.
        shutil.rmtree(plugin_root)
        touched.append(f"{plugin_root.relative_to(ROOT)} (removed, no skills left)")


def _unregister_published(plugin: str, skill: str, retires_plugin: bool, touched: list[str]) -> None:
    path = ROOT / "scripts" / "validate-repository.py"
    text = path.read_text(encoding="utf-8")
    match = re.search(rf'^    "{plugin}": \[([^\]]*)\],$', text, re.MULTILINE)
    if not match:
        raise SystemExit(f"error: {plugin} is not listed in PUBLISHED")
    if retires_plugin:
        updated = text.replace(f"{match.group(0)}\n", "", 1)
    else:
        names = sorted(set(re.findall(r'"([^"]+)"', match.group(1))) - {skill})
        listed = ", ".join(f'"{name}"' for name in names)
        updated = text.replace(match.group(0), f'    "{plugin}": [{listed}],', 1)
    path.write_text(updated, encoding="utf-8")
    touched.append(f"{path.relative_to(ROOT)} (updated)")


def _unregister_root_readme(plugin: str, skill: str, touched: list[str]) -> None:
    path = ROOT / "README.md"
    marker = f"plugins/{plugin}/skills/{skill}/SKILL.md"
    _drop_lines(path, lambda line: marker in line, touched)


def _unregister_plugin_readme(path: Path, skill: str, touched: list[str]) -> None:
    marker = f"({skill}/SKILL.md)"
    _drop_lines(path, lambda line: marker in line, touched)


def _drop_lines(path: Path, matches, touched: list[str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if not matches(line)]
    if len(kept) == len(lines):
        raise SystemExit(f"error: found nothing to remove in {path.relative_to(ROOT)}")
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    touched.append(f"{path.relative_to(ROOT)} (updated)")


def _unregister_plugin_manifest(plugin_root: Path, skill: str, touched: list[str]) -> None:
    path = plugin_root / ".claude-plugin" / "plugin.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["skills"] = [entry for entry in manifest["skills"] if entry != f"./skills/{skill}"]
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    touched.append(f"{path.relative_to(ROOT)} (updated)")


def _unregister_marketplace(plugin: str, touched: list[str]) -> None:
    path = ROOT / ".claude-plugin" / "marketplace.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["plugins"] = [entry for entry in manifest["plugins"] if entry["name"] != plugin]
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    touched.append(f"{path.relative_to(ROOT)} (updated)")


def _unregister_version_bump(plugin: str, skill: str, retires_plugin: bool, touched: list[str]) -> None:
    path = ROOT / ".version-bump.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["text"] = [
        entry for entry in config["text"] if entry != f"plugins/{plugin}/skills/{skill}/SKILL.md"
    ]
    if retires_plugin:
        manifest = f"plugins/{plugin}/.claude-plugin/plugin.json"
        config["json"] = [entry for entry in config["json"] if entry["path"] != manifest]
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    touched.append(f"{path.relative_to(ROOT)} (updated)")


def _drop_dangling_hand_offs(skill: str, touched: list[str]) -> None:
    """Clear routes_to entries pointing at the retired skill, keeping the cases.

    A non-trigger stays true after the skill it named is gone — the prompt still
    must not fire the skill whose suite it lives in. Only the hand-off is stale.
    """

    for path in sorted(EVALS_ROOT.glob("*/evals.json")):
        suite = json.loads(path.read_text(encoding="utf-8"))
        dangling = [case for case in suite.get("non_triggers", []) if case.get("routes_to") == skill]
        if not dangling:
            continue
        for case in dangling:
            del case["routes_to"]
        path.write_text(
            json.dumps(suite, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        touched.append(f"{path.relative_to(ROOT)} ({len(dangling)} hand-off cleared)")


def _unregister_skills_sh(plugin: str, skill: str, touched: list[str]) -> None:
    path = ROOT / "skills.sh.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    # Titles are title-cased for the directory page; see new-skill.py.
    title = plugin.replace("-", " ").title()
    for group in config["groupings"]:
        if group["title"] == title:
            group["skills"] = [name for name in group["skills"] if name != skill]
    config["groupings"] = [group for group in config["groupings"] if group["skills"]]
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    touched.append(f"{path.relative_to(ROOT)} (updated)")


if __name__ == "__main__":
    raise SystemExit(main())
