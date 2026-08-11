#!/usr/bin/env python3
"""Build registry.json — the one machine-readable view of the published catalogue.

Anything rendering this catalogue outside Claude Code (the personal site, a
directory, a future dashboard) needs the same four facts every time: what the
groups are, what is in them, what each skill claims about itself, and how to
install it. Without a published contract each reader parses plugins/ itself,
which hands the repository's internal layout to code nobody here can see — a
directory rename then breaks a site that was never tested against this tree.

So the repository states it once, and readers fetch the statement:

  python3 scripts/build-registry.py            Write registry.json
  python3 scripts/build-registry.py --check    Fail if the committed file is stale
  python3 scripts/build-registry.py --stdout   Print it without writing

Nothing here is authored. Every field is lifted from a file that already had to
declare it — skills.sh.json for the grouping and its prose, marketplace.json for
the category and the marketplace name, each plugin.json for the summary and
keywords, and each SKILL.md for the skill itself. Adding a field to this file
that no other file declares would make it an eighth registry to keep in step.

The output is deterministic: no timestamp, no commit, no build id. That is what
makes `--check` mean something — CI regenerates and compares bytes, so a skill
edited without regenerating fails the build instead of silently serving a stale
catalogue to whoever fetches it. A timestamp would make every run differ and
turn the check into noise.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
MARKETPLACE_MANIFEST = ROOT / ".claude-plugin" / "marketplace.json"
GROUPING_MANIFEST = ROOT / "skills.sh.json"
REGISTRY = ROOT / "registry.json"

# Bumped when a consumer would have to change to keep reading this file. Adding
# an optional field is not that; removing or repurposing one is.
SCHEMA_VERSION = 1

# The branch a source link resolves against. A tag would send the reader to an
# archived copy of a skill they cannot install, so the link follows the default
# branch — the same ref the marketplace installs from.
SOURCE_REF = "main"


def _load_validator() -> ModuleType:
    """Import the validator, for the frontmatter parser it already owns.

    A second parser here would be a second opinion about what frontmatter means,
    and the registry would publish fields the validator never checked.
    """

    path = ROOT / "scripts" / "validate-repository.py"
    spec = importlib.util.spec_from_file_location("validate_repository", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"error: cannot load {path.relative_to(ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit(f"error: cannot read {path.relative_to(ROOT)}: {error}") from error


def _skill_directories() -> dict[str, Path]:
    """Return {skill name: directory} for every skill on disk.

    Skill names are unique across the marketplace — `/plugin install` and the
    grouping manifest both key on the bare name — so a collision is a defect the
    caller has to hear about rather than a case to disambiguate.
    """

    found: dict[str, Path] = {}
    for skill_file in sorted(PLUGINS_ROOT.glob("*/skills/*/SKILL.md")):
        name = skill_file.parent.name
        if name in found:
            raise SystemExit(
                f"error: two skills are both named {name!r}: "
                f"{found[name].relative_to(ROOT)} and {skill_file.parent.relative_to(ROOT)}"
            )
        found[name] = skill_file.parent
    return found


def _body(text: str) -> str:
    """Return the prose below the closing frontmatter delimiter."""

    lines = text.splitlines()
    return "\n".join(lines[lines.index("---", 1) + 1 :]).lstrip("\n")


def _skill_entry(name: str, directory: Path, validator: ModuleType, repository: str) -> dict:
    skill_file = directory / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")

    errors: list[str] = []
    frontmatter = validator._parse_frontmatter(text, skill_file, errors)
    if errors:
        raise SystemExit(
            f"error: {skill_file.relative_to(ROOT)} has frontmatter the validator rejects:\n  "
            + "\n  ".join(errors)
        )

    metadata = frontmatter.get("metadata")
    relative = directory.relative_to(ROOT).as_posix()
    entry = {
        "name": name,
        "description": frontmatter.get("description", ""),
        "license": frontmatter.get("license", ""),
        "version": metadata.get("version", "") if isinstance(metadata, dict) else "",
        "path": relative,
        "sourceUrl": f"{repository}/blob/{SOURCE_REF}/{relative}/SKILL.md",
        "body": _body(text),
    }
    # Optional in the frontmatter, so optional here: a skill taking no arguments
    # should not publish an empty string every renderer then special-cases.
    if "argument-hint" in frontmatter:
        entry["argumentHint"] = frontmatter["argument-hint"]
    return entry


def build() -> dict:
    validator = _load_validator()
    marketplace = _read_json(MARKETPLACE_MANIFEST)
    grouping = _read_json(GROUPING_MANIFEST)
    directories = _skill_directories()

    marketplace_name = marketplace["name"]
    categories = {
        entry["name"]: entry["category"]
        for entry in marketplace.get("plugins", [])
        if isinstance(entry, dict) and "category" in entry
    }

    groups: list[dict] = []
    grouped: set[str] = set()
    repositories: set[str] = set()
    for group in grouping.get("groupings", []):
        names = group.get("skills", [])
        missing = [name for name in names if name not in directories]
        if missing:
            raise SystemExit(
                f"error: skills.sh.json group {group['title']!r} lists {', '.join(missing)},"
                " which is not on disk"
            )

        # Checked before the plugin is derived: an emptied group derives no
        # plugin at all, and reporting that as spanning zero plugins names the
        # symptom rather than the edit that caused it.
        if not names:
            raise SystemExit(
                f"error: skills.sh.json group {group['title']!r} lists no skills."
                " Remove the group, or file a skill under it."
            )

        # The grouping manifest keys on bare skill names, so which plugin a group
        # belongs to is derived rather than declared. A group spanning two plugins
        # has no single category, install string or manifest to read — that is a
        # grouping mistake, not a shape to support.
        plugins = {directories[name].parents[1].name for name in names}
        if len(plugins) != 1:
            raise SystemExit(
                f"error: skills.sh.json group {group['title']!r} spans plugins "
                f"{', '.join(sorted(plugins))}; a group is one plugin's skills"
            )
        plugin = plugins.pop()
        manifest = _read_json(PLUGINS_ROOT / plugin / "plugin.json")
        repositories.add(manifest["repository"])

        grouped.update(names)
        groups.append(
            {
                "id": plugin,
                "title": group["title"],
                "description": group["description"],
                "summary": manifest["description"],
                "category": categories.get(plugin, ""),
                "keywords": manifest.get("keywords", []),
                "install": f"/plugin install {plugin}@{marketplace_name}",
                "skills": [
                    _skill_entry(name, directories[name], validator, manifest["repository"]) for name in names
                ],
            }
        )

    # `notGrouped: bottom` is skills.sh's rendering fallback for a skill nobody
    # filed. Here it would publish a skill under no heading, which is how a new
    # skill reaches a reader's page uncategorised and stays that way.
    ungrouped = sorted(set(directories) - grouped)
    if ungrouped:
        raise SystemExit(
            f"error: {', '.join(ungrouped)} on disk but in no skills.sh.json group."
            " Add it to a grouping before publishing."
        )

    if len(repositories) != 1:
        raise SystemExit(
            f"error: the plugin manifests declare {len(repositories)} different repositories:"
            f" {', '.join(sorted(repositories))}"
        )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "marketplace": marketplace_name,
        "version": validator.VERSION,
        "repository": repositories.pop(),
        "groups": groups,
    }


def serialise(registry: dict) -> str:
    # ensure_ascii=False because a third of these descriptions carry the Chinese
    # trigger phrasings that make the skills fire; escaped, they are unreadable
    # in review and three times the bytes over the wire.
    return json.dumps(registry, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="fail if the committed file is stale")
    group.add_argument("--stdout", action="store_true", help="print instead of writing")
    args = parser.parse_args()

    registry = build()
    rendered = serialise(registry)
    where = REGISTRY.relative_to(ROOT)

    if args.stdout:
        sys.stdout.write(rendered)
        return 0

    if args.check:
        if not REGISTRY.is_file():
            print(f"error: {where} does not exist; run scripts/build-registry.py", file=sys.stderr)
            return 1
        if REGISTRY.read_text(encoding="utf-8") != rendered:
            print(
                f"error: {where} is stale. The catalogue changed without it being rebuilt —"
                " run scripts/build-registry.py and commit the result.",
                file=sys.stderr,
            )
            return 1
        print(f"{where} is current")
        return 0

    REGISTRY.write_text(rendered, encoding="utf-8")
    skills = sum(len(group["skills"]) for group in registry["groups"])
    print(f"wrote {where}: {skills} skills in {len(registry['groups'])} groups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
