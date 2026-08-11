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
import re
import sys
from pathlib import Path
from types import ModuleType

# Same words check-descriptions.py rejects in a description, for the same reason.
PLACEHOLDER = re.compile(r"(?i)\bplaceholder\b|\bTODO\b|\bFIXME\b")

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
MARKETPLACE_MANIFEST = ROOT / ".claude-plugin" / "marketplace.json"
GROUPING_MANIFEST = ROOT / "skills.sh.json"
TRANSLATIONS = ROOT / "i18n"
REGISTRY = ROOT / "registry.json"

# Locales carried alongside the English. Adding one means adding i18n/<code>.json
# with an entry for every group and every skill — the build fails until it is
# complete, which is the only thing that stops a translation going quietly stale
# while the page keeps serving it.
LOCALES = ("zh",)

# What a translated entry has to provide. `overview` is the one field with no
# English counterpart: SKILL.md bodies stay in English because they are what the
# agent executes, so a reader who does not read English gets this instead.
GROUP_FIELDS = ("title", "description", "summary")
SKILL_FIELDS = ("description", "overview")

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


def _translations(groups: dict[str, list[str]]) -> dict[str, dict]:
    """Load every locale, and hold each to covering exactly what is published.

    Both directions are errors. A missing entry ships a page that silently falls
    back to English for one skill among thirteen translated ones, which reads as
    an oversight nobody notices; a leftover entry is a skill that was retired
    with its translation left behind, and the next skill to reuse the name would
    inherit it.
    """

    loaded: dict[str, dict] = {}
    for locale in LOCALES:
        path = TRANSLATIONS / f"{locale}.json"
        if not path.is_file():
            raise SystemExit(f"error: {path.relative_to(ROOT)} does not exist, but {locale} is published")
        data = _read_json(path)
        errors: list[str] = []

        published_groups = set(groups)
        translated_groups = set(data.get("groups", {}))
        for name in sorted(published_groups - translated_groups):
            errors.append(f"group {name!r} has no {locale} entry")
        for name in sorted(translated_groups - published_groups):
            errors.append(f"group {name!r} is translated but not published")

        published_skills = {skill for names in groups.values() for skill in names}
        translated_skills = set(data.get("skills", {}))
        for name in sorted(published_skills - translated_skills):
            errors.append(f"skill {name!r} has no {locale} entry")
        for name in sorted(translated_skills - published_skills):
            errors.append(f"skill {name!r} is translated but not published")

        # Empty and still-scaffolded are the same failure with different
        # symptoms: one renders a blank, the other renders the word PLACEHOLDER
        # to a reader. The scaffold writes these deliberately, the same way it
        # writes a description the validator rejects — everything mechanical is
        # done, and the one part that needs a person is not marked done for them.
        for name, entry in sorted(data.get("groups", {}).items()):
            for field in GROUP_FIELDS:
                value = entry.get(field, "")
                if not value.strip():
                    errors.append(f"group {name!r} is missing {locale}.{field}")
                elif PLACEHOLDER.search(value):
                    errors.append(f"group {name!r} still has the scaffolded {locale}.{field}")
        for name, entry in sorted(data.get("skills", {}).items()):
            for field in SKILL_FIELDS:
                value = entry.get(field, "")
                if not value.strip():
                    errors.append(f"skill {name!r} is missing {locale}.{field}")
                elif PLACEHOLDER.search(value):
                    errors.append(f"skill {name!r} still has the scaffolded {locale}.{field}")

        if errors:
            raise SystemExit(
                f"error: {path.relative_to(ROOT)} does not match the published catalogue:\n  "
                + "\n  ".join(errors)
            )
        loaded[locale] = data
    return loaded


def _localised(translations: dict[str, dict], section: str, name: str, fields: tuple[str, ...]) -> dict:
    """Return {locale: {field: text}} for one group or skill.

    Nested under the entry rather than held as a parallel tree, so a reader
    picking a locale never has to join two structures and never has half of one.
    """

    return {
        locale: {field: data[section][name][field] for field in fields}
        for locale, data in translations.items()
    }


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
        # Filled after the structural checks — see the injection site in build().
        "i18n": {},
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

    published: dict[str, list[str]] = {}
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
        published[plugin] = list(names)
        groups.append(
            {
                "id": plugin,
                "title": group["title"],
                "description": group["description"],
                "summary": manifest["description"],
                "category": categories.get(plugin, ""),
                "keywords": manifest.get("keywords", []),
                "install": f"/plugin install {plugin}@{marketplace_name}",
                # Filled once the structure below has been checked — see the note
                # at the injection site.
                "i18n": {},
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

    # Last, and deliberately: a tree with a structural problem — a skill in no
    # group, a group spanning two plugins — reports that problem, not the
    # translation gap that follows from it. Checking here also means the
    # translations are held to the catalogue as published rather than to a
    # half-resolved view of it.
    translations = _translations(published)
    for group in groups:
        group["i18n"] = _localised(translations, "groups", group["id"], GROUP_FIELDS)
        for skill in group["skills"]:
            skill["i18n"] = _localised(translations, "skills", skill["name"], SKILL_FIELDS)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "marketplace": marketplace_name,
        "version": validator.VERSION,
        "repository": repositories.pop(),
        # Declared rather than inferred from the first entry's keys: a reader
        # deciding which languages to offer should not have to guess from a
        # sample, and an empty catalogue still has to answer the question.
        "locales": list(LOCALES),
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
