#!/usr/bin/env python3
"""Validate repository metadata, registries, published skills, and tests."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
TESTS_ROOT = ROOT / "tests"
MARKETPLACE_MANIFEST = ROOT / ".claude-plugin" / "marketplace.json"
VERSION = "0.15.0"

# Lowercase letters, digits and hyphens. Claude Code is lenient about a plugin
# or marketplace name; the claude.ai marketplace sync is not, and a keyword that
# does not match is one a plugin directory will not surface.
KEBAB_CASE = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")

# The published surface, asserted exactly: a plugin or skill that appears on disk
# without being added here is unregistered somewhere, and one listed here without
# appearing on disk has been dropped.
PUBLISHED = {
    "photography": ["photo-abstract-editorial-native"],
    "brand": ["logo-banner"],
    "chinese-metaphysics": [
        "bazi-chart",
        "bazi-compatibility",
        "bazi-compatibility-reading",
        "bazi-reading",
        "bazi-ziwei-cross",
        "ziwei-chart",
        "ziwei-reading",
    ],
    "astrology": ["natal-chart", "natal-reading", "synastry", "synastry-reading"],
    "dev": ["cleanup", "handoff", "retitle", "reunite", "ship", "steward", "sync"],
    "docs": ["repo-polish"],
    "writing": ["email", "personal-blog", "tempering"],
}
# Exceptions only. MIT is what new-skill.py stamps on a new plugin and what
# every plugin carries unless a dependency forces otherwise, so listing the MIT
# ones restates the default and makes this look like a registry that has to be
# complete — it is not, and a plugin missing from it is not a bug. astrology is
# here because pyswisseph is AGPL and a skill cannot be licensed more loosely
# than the library it imports.
DEFAULT_LICENSE = "MIT"
PLUGIN_LICENSE_EXCEPTIONS = {
    "astrology": "AGPL-3.0-or-later",
}

# Other people's plugins, registered so they install from this marketplace too.
# Nothing below the marketplace entry reaches them: no tree here, no plugin.json
# to version, no README bullet with a local path, and no CI route — the install
# workflow derives its list from plugins/ on disk, so a bookmark whose owner
# rewrites their repository cannot turn this repository's build red.
BOOKMARKED = {
    "codex",
    "everything-claude-code",
    "i-have-adhd",
    "mattpocock-skills",
    "obsidian",
    "warp",
}
# The sha is the whole guarantee. An entry pinned to a branch installs whatever
# that repository holds at install time, which hands its owner — or anyone who
# takes it over — a write path into every agent that trusts this marketplace.
COMMIT_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
REMOTE_SOURCE_KINDS = {"git-subdir", "url"}

# The second manifest, for the readers Claude Code is not. Claude Code reads
# .claude-plugin/plugin.json; ChatGPT, Codex, Cursor, Copilot, Kiro and VS Code
# read Agent Plugins' plugin.json at the plugin root. Neither file is derived
# from the other, so the fields they share are asserted equal here and the
# bumper moves both — a plugin described two ways drifts otherwise.
#
# The spec version is deliberately not written down in this file. It appears
# inside the $schema URL as a semver, and every declared version here is moved
# by a plain string replace: a release that reached that same number would
# rewrite the URL with it. The URL is held to its shape instead, and the four
# manifests are held to declaring one identical schema.
AGENT_PLUGIN_SCHEMA = re.compile(r"\Ahttps://agent-plugins\.org/schemas/\d+\.\d+\.\d+/plugin\.schema\.json\Z")
# The schema is closed: a field outside this set does not conform, and clients
# are required to report it. `skills` is absent because the skills tree is found
# by reading skills/ rather than by declaring it, and `dependencies` is absent
# because the spec has no such concept — which is why the bundle, whose whole
# content is a dependency list, ships no portable manifest.
AGENT_PLUGIN_FIELDS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
AGENT_PLUGIN_SHARED = ("name", "version", "description", "license", "author")
REPOSITORY_URL = "https://github.com/Misoto22/skills"
# What a client's plugin directory searches on. Held to KEBAB_CASE so a search
# matches whatever a person typed, and held off the plugin's own name — a
# directory already indexes that, so restating it buys no reach and crowds out
# a term that would have.
MINIMUM_KEYWORDS = 3
# Where a client puts what only it understands. Nothing here uses it yet, and
# the shape is guarded anyway: the one thing a namespace has to do is not
# collide, which a bare word cannot promise and a domain someone owns can.
#
# `agents/openai.yaml` is not a candidate to move here. It sits inside a skill
# and describes that skill to one client; these namespaces sit at the plugin
# root and describe the plugin. Different scopes, and the `npx skills add`
# route reads the file where it is.
EXTENSION_NAMESPACE = re.compile(r"\A[a-z0-9-]+(?:\.[a-z0-9-]+)+\Z")

# One entry installs the rest, by depending on every plugin above. It carries no
# skills, so it sits outside plugins/ where the packager, list-skills.sh, and the
# per-skill install routes cannot mistake it for one. Its dependency list is
# asserted against both registries: a bookmark added without a matching entry
# here would be a plugin the one-command install silently skips.
#
# Those dependencies are spelled `<plugin>@<marketplace>`, which is why the
# marketplace name is read from the manifest rather than declared here. It is
# also the install suffix a user types, so it reaches the scaffold, the
# retirement, the install workflow and both READMEs; one file declares it and
# every other reader asks that file. See marketplace_name().
BUNDLE = "all"
BUNDLE_ROOT = ROOT / "bundle"

# What `/plugin` groups an entry under while browsing. The vocabulary is the one
# Anthropic's own catalogue uses, so an entry here sorts alongside the rest of a
# user's marketplaces rather than into a category of one. The bundle is exempt:
# it is an entry point to the others, not a subject anyone browses for.
CATEGORIES = {
    "automation",
    "database",
    "deployment",
    "design",
    "development",
    "learning",
    "monitoring",
    "productivity",
    "security",
    "testing",
}
TEXT_SUFFIXES = {".md", ".json", ".py", ".txt", ".yaml", ".yml", ".sh"}
FORBIDDEN_RUNTIME_TEXT = (
    "/Users/",
    "/home/",
    "smtp.gmail.com",
    "provider-specific mail command",
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _english_quantity(value: int) -> str:
    """Spell a count the way the English README writes it."""

    ones = ("", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
    teens = (
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
    )
    tens = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
    if value >= 100:
        return str(value)
    if value < 10:
        return ones[value]
    if value < 20:
        return teens[value - 10]
    ten, one = divmod(value, 10)
    return tens[ten] + (f"-{ones[one]}" if one else "")


def _chinese_quantity(value: int) -> str:
    """Spell a count the way the Chinese README writes it."""

    digits = "〇一二三四五六七八九"
    if value >= 100:
        return str(value)
    if value < 10:
        return digits[value]
    ten, one = divmod(value, 10)
    return f"{'' if ten == 1 else digits[ten]}十{digits[one] if one else ''}"


# A count written into prose is a registry too, and it was the one nothing read:
# both READMEs said "twelve skills" for two releases after the thirteenth
# shipped, with every other check green. The count now appears once per README —
# the two other sentences carrying it were anaphoric and lost nothing — and each
# language declares how its own numerals are read. A translation with no entry
# here fails rather than going quietly stale, which is the rule the rest of the
# registry is already held to.
STATED_COUNTS = {
    "README.md": (
        re.compile(r"(?m)^(?P<skills>[A-Za-z-]+) skills in (?P<plugins>[A-Za-z-]+) plugins\b"),
        _english_quantity,
    ),
    "README.zh-CN.md": (
        # The fullwidth comma is the one in the sentence being matched, not a
        # mistyped ASCII one; RUF001 cannot tell the difference.
        re.compile(
            r"(?P<plugins>[〇一二三四五六七八九十]+)个 plugin，"  # noqa: RUF001
            r"(?P<skills>[〇一二三四五六七八九十]+)个 skill"
        ),
        _chinese_quantity,
    ),
}
SKILL_REFERENCE = re.compile(r"[\w-]+/SKILL\.md")
PUBLISHED_REFERENCE = re.compile(r"plugins/[\w-]+/skills/[\w-]+/SKILL\.md")
# Retired and unfinished material lives outside plugins/, so no installer, no
# packager, and no registry sees it. It is held to one rule: stay unlisted.
RETIRED_ROOTS = ("drafts", "deprecated")

# Only Claude Code expands ${CLAUDE_*}, and only Claude Code's plugin cache keeps
# a directory above the skill. Anything a skill reads must resolve from the skill
# root on every installer, so both forms are rejected in published content.
NON_PORTABLE_TEXT = (
    ("${CLAUDE_", "host-specific variable"),
    ("../", "path escaping the skill"),
)


def marketplace_name() -> str:
    """Return the marketplace name, from the one file that has to declare it.

    Every other reader — the scaffold, the retirement, the install workflow, the
    contract tests — calls this or reads the same field, rather than restating
    `misoto22`. The name is the install suffix a user types, so a second copy of
    it is a rename that half the repository silently does not follow.
    """

    return str(json.loads(MARKETPLACE_MANIFEST.read_text(encoding="utf-8"))["name"])


def restate_counts() -> list[str]:
    """Move the count each README states to match the tree, and report what moved.

    The one writer for the one reader above. `new-skill.py` and `remove-skill.py`
    call it, because a check the tooling cannot satisfy is a chore rather than a
    guard: scaffolding a skill would otherwise leave a failing build for the
    author to fix by hand, in prose, in every translation.
    """

    counts = {
        "skills": len(list(PLUGINS_ROOT.glob("*/skills/*/SKILL.md"))),
        "plugins": len(list(PLUGINS_ROOT.glob("*/.claude-plugin/plugin.json"))),
    }
    changed: list[str] = []
    for path in sorted(ROOT.glob("README*.md")):
        declared = STATED_COUNTS.get(path.name)
        if declared is None:
            continue
        pattern, numeral = declared
        text = path.read_text(encoding="utf-8")
        match = pattern.search(text)
        if match is None:
            continue

        # Rebuilt from the group spans rather than by string replacement: two
        # nouns can state the same numeral, and replacing it would rewrite
        # whichever came first instead of the one that moved.
        pieces: list[str] = []
        cursor = match.start()
        for noun in sorted(counts, key=match.start):
            start, end = match.span(noun)
            stated = match.group(noun)
            wanted = numeral(counts[noun])
            pieces.append(text[cursor:start])
            pieces.append(wanted.capitalize() if stated[:1].isupper() else wanted)
            cursor = end
        pieces.append(text[cursor : match.end()])

        updated = text[: match.start()] + "".join(pieces) + text[match.end() :]
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(path.name)
    return changed


def validate_repository(*, run_tests: bool) -> list[str]:
    errors: list[str] = []
    marketplace = _load_json(MARKETPLACE_MANIFEST, errors)
    # Every root README, not only the English one. A translation becomes a second
    # registry the moment it lists skills, and one nothing checks goes stale on the
    # next skill added — silently, because the file it was translated from is the
    # only one CI was reading.
    root_readmes = {path.name: _read_text(path, errors) for path in sorted(ROOT.glob("README*.md"))}
    if "README.md" not in root_readmes:
        errors.append("README.md is missing")

    found_plugins = sorted(
        path.parent.parent.name for path in PLUGINS_ROOT.glob("*/.claude-plugin/plugin.json")
    )
    if found_plugins != sorted(PUBLISHED):
        errors.append(f"published plugins must be {sorted(PUBLISHED)}; found {found_plugins}")

    # Both manifests, over the same set. A plugin carrying one and not the other
    # installs on half the clients this repository claims to support, and which
    # half is invisible from either file on its own.
    found_portable = sorted(path.parent.name for path in PLUGINS_ROOT.glob("*/plugin.json"))
    if found_portable != sorted(PUBLISHED):
        errors.append(f"Agent Plugins manifests must be {sorted(PUBLISHED)}; found {found_portable}")

    # Held to a shape, not to a literal: the literal would be the same name
    # written down a second time, which is the thing this file exists to stop.
    name = marketplace.get("name")
    if not isinstance(name, str) or not KEBAB_CASE.match(name):
        errors.append(f"marketplace name must be kebab-case; found {name!r}")
        name = ""
    metadata = marketplace.get("metadata")
    # pluginRoot is the one field the two installers read differently: Claude Code
    # resolves a source against the repository root regardless, while the skills
    # CLI prepends pluginRoot to it. No single source satisfies both while it is
    # set, so it stays absent and every source carries the full path.
    if not isinstance(metadata, dict) or "pluginRoot" in metadata:
        errors.append("marketplace metadata must not set pluginRoot")
    entries = marketplace.get("plugins")
    entries = entries if isinstance(entries, list) else []
    # The skills CLI derives its plugin grouping from these skill paths. An entry
    # without them groups nothing, and the install picker degrades to a flat list
    # of skill names with no plugin to read them against.
    registered = {
        entry.get("name"): (entry.get("source"), entry.get("skills"))
        for entry in entries
        if isinstance(entry, dict)
    }
    expected_entries = {
        name: (f"./plugins/{name}", [f"./skills/{skill}" for skill in skills])
        for name, skills in PUBLISHED.items()
    }
    published_entries = {
        name: entry for name, entry in registered.items() if name not in BOOKMARKED and name != BUNDLE
    }
    if published_entries != expected_entries:
        errors.append(f"marketplace must register exactly {expected_entries}; found {published_entries}")
    _validate_bundle(registered.get(BUNDLE), name, errors)
    for entry in entries:
        name = entry.get("name") if isinstance(entry, dict) else None
        if name is None or name == BUNDLE:
            continue
        category = entry.get("category")
        if category not in CATEGORIES:
            expected = sorted(CATEGORIES)
            errors.append(f"{name} category must be one of {expected}; found {category!r}")
    bookmarked = sorted(name for name in registered if name in BOOKMARKED)
    if bookmarked != sorted(BOOKMARKED):
        errors.append(f"marketplace must bookmark exactly {sorted(BOOKMARKED)}; found {bookmarked}")
    for name in bookmarked:
        _validate_bookmark(name, registered[name], errors)

    declared_schemas: set[str] = set()
    for plugin_name, expected_skills in sorted(PUBLISHED.items()):
        plugin_root = PLUGINS_ROOT / plugin_name
        skills_root = plugin_root / "skills"
        plugin_license = PLUGIN_LICENSE_EXCEPTIONS.get(plugin_name, DEFAULT_LICENSE)
        skill_paths = sorted(path.parent for path in skills_root.glob("*/SKILL.md"))
        names = [path.name for path in skill_paths]
        if names != expected_skills:
            errors.append(f"{plugin_name} skills must be {expected_skills}; found {names}")

        plugin = _load_json(plugin_root / ".claude-plugin" / "plugin.json", errors)
        if plugin.get("skills") != [f"./skills/{name}" for name in names]:
            errors.append(f"{plugin_name} skill paths do not match its published skills tree")
        for field, expected in (
            ("name", plugin_name),
            ("version", VERSION),
            ("license", plugin_license),
        ):
            if plugin.get(field) != expected:
                errors.append(f"{plugin_name} plugin {field} must be {expected!r}")
        author = plugin.get("author")
        if not isinstance(author, dict) or author.get("name") != "skills contributors":
            errors.append(f"{plugin_name} plugin author must identify 'skills contributors'")

        _validate_agent_plugin(plugin_root, plugin, declared_schemas, errors)

        skills_readme = _read_text(skills_root / "README.md", errors)
        for name in names:
            for readme_name, readme in root_readmes.items():
                if f"plugins/{plugin_name}/skills/{name}/SKILL.md" not in readme:
                    errors.append(f"{readme_name} does not register {plugin_name}/{name}")
            if f"{name}/SKILL.md" not in skills_readme:
                errors.append(f"{plugin_name} skills/README.md does not register {name}")

        # The registries say every published skill is listed. This says every
        # listing is a published skill, which is what a retirement gets wrong.
        for reference in SKILL_REFERENCE.findall(skills_readme):
            if not (skills_root / reference).is_file():
                errors.append(f"{plugin_name} skills/README.md lists {reference}, which is gone")

        for skill_path in skill_paths:
            _validate_skill(skill_path, plugin_license, errors)

        # shared/ ships inside every published skill, so it is held to the same
        # runtime-neutrality rule as the skills that read it.
        _validate_runtime_text(plugin_root / "shared", errors)

    _validate_scripts_are_tested(errors)

    # One spec version across the repository. Half the plugins targeting an older
    # schema is a release nobody meant to make, and each manifest reads correct.
    if len(declared_schemas) > 1:
        errors.append(f"plugins target more than one Agent Plugins schema: {sorted(declared_schemas)}")

    published_counts = {
        "skills": sum(len(skills) for skills in PUBLISHED.values()),
        "plugins": len(PUBLISHED),
    }
    for readme_name, readme in root_readmes.items():
        _validate_stated_counts(readme_name, readme, published_counts, errors)

        for reference in PUBLISHED_REFERENCE.findall(readme):
            if not (ROOT / reference).is_file():
                errors.append(f"{readme_name} links {reference}, which does not exist")

        # Every other relative link too. The skill links above are held to the
        # registry, and links inside a skill are resolved by _validate_skill —
        # between them sat CONTRIBUTING.md, AGENTS.md, docs/email.md and
        # skills.sh.json, which a rename breaks with the build still green.
        for target in MARKDOWN_LINK.findall(_strip_fenced_blocks(readme)):
            if target.startswith(("https://", "http://", "#", "mailto:")):
                continue
            relative = target.split("#", 1)[0]
            if not relative or not (ROOT / relative).is_file():
                errors.append(f"{readme_name} links {target}, which does not resolve")

        for retired_root in RETIRED_ROOTS:
            for skill_file in sorted((ROOT / retired_root).rglob("SKILL.md")):
                relative = skill_file.relative_to(ROOT).as_posix()
                if relative in readme:
                    errors.append(f"{readme_name} lists {relative}, which is not published")

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync-shared.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        errors.append("vendored shared/ copies are stale; run scripts/sync-shared.py")

    # The description decides whether a skill ever fires, and it is the one field
    # a structural check cannot judge. Its rules live in their own script; the
    # violations are surfaced here rather than reduced to one line.
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-descriptions.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        errors.extend(line.removeprefix("error: ") for line in result.stderr.splitlines() if line.strip())

    if run_tests and not errors:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=ROOT,
            check=False,
        )
        if result.returncode != 0:
            errors.append("unit test suite failed")
    return errors


def _validate_scripts_are_tested(errors: list[str]) -> None:
    """Every shipped script module has to be named by something under tests/.

    AGENTS.md has always said a skill shipping `scripts/` also requires unit
    tests, and nothing checked it. The coverage floor is the only thing that
    noticed, and only for an addition large enough to move the number.

    Named, not imported: tests reach these modules by path and by
    `importlib.util.spec_from_file_location`, so there is no import graph to
    read. The stem appearing somewhere under tests/ is the weakest claim that
    cannot be satisfied by accident, and it is checked against the module a
    plugin actually ships rather than against a directory naming convention —
    two bazi skills share one test package, and that is fine.
    """

    tested = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore") for path in sorted(TESTS_ROOT.rglob("*.py"))
    )
    for script in sorted(PLUGINS_ROOT.glob("*/skills/*/scripts/*.py")):
        if script.stem.startswith("__"):
            continue
        if not re.search(rf"\b{re.escape(script.stem)}\b", tested):
            relative = script.relative_to(ROOT).as_posix()
            errors.append(
                f"{relative}: no test under tests/ names {script.stem!r}."
                " A skill shipping scripts/ requires unit tests; see AGENTS.md."
            )


def _validate_stated_counts(
    readme_name: str,
    readme: str,
    counts: dict[str, int],
    errors: list[str],
) -> None:
    """Hold the one count each README writes out to the tree it describes."""

    declared = STATED_COUNTS.get(readme_name)
    if declared is None:
        errors.append(
            f"{readme_name}: no count pattern is registered for it in STATED_COUNTS."
            " A README that states a total nothing reads is the drift this catches."
        )
        return
    pattern, numeral = declared
    match = pattern.search(readme)
    if match is None:
        expected = ", ".join(f"{numeral(total)} {noun}" for noun, total in counts.items())
        errors.append(f"{readme_name}: states no published count; the tree has {expected}")
        return
    for noun, total in counts.items():
        stated = match.group(noun)
        if stated.lower() != numeral(total):
            errors.append(
                f"{readme_name}: states {stated!r} {noun}; the tree has {total}, {numeral(total)!r}"
            )


def _validate_bundle(entry: tuple[object, object] | None, name: str, errors: list[str]) -> None:
    """The one-command install: an entry that carries nothing but dependencies."""

    if entry is None:
        errors.append(f"marketplace must register the {BUNDLE!r} bundle")
        return
    source, skills = entry
    if source != "./bundle":
        errors.append(f"{BUNDLE} bundle source must be './bundle'; found {source!r}")
    if skills is not None:
        errors.append(f"{BUNDLE} bundle carries no skills of its own")

    manifest = _load_json(BUNDLE_ROOT / ".claude-plugin" / "plugin.json", errors)
    for field, expected in (
        ("name", BUNDLE),
        ("version", VERSION),
        ("license", DEFAULT_LICENSE),
    ):
        if manifest.get(field) != expected:
            errors.append(f"{BUNDLE} bundle {field} must be {expected!r}")
    author = manifest.get("author")
    if not isinstance(author, dict) or author.get("name") != "skills contributors":
        errors.append(f"{BUNDLE} bundle author must identify 'skills contributors'")
    if manifest.get("skills") is not None:
        errors.append(f"{BUNDLE} bundle must declare no skills path")

    # Both registries, in one list. A plugin registered but left out here is one
    # the advertised single command quietly does not install.
    expected_dependencies = sorted(f"{plugin}@{name}" for plugin in (*PUBLISHED, *BOOKMARKED))
    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, list) or sorted(dependencies) != expected_dependencies:
        errors.append(f"{BUNDLE} bundle must depend on exactly {expected_dependencies}")


def _validate_agent_plugin(
    plugin_root: Path,
    claude_manifest: dict[str, object],
    declared_schemas: set[str],
    errors: list[str],
) -> None:
    """Hold the portable manifest to the closed schema, and to the Claude one.

    Nothing generates one file from the other, so the only thing keeping a plugin
    from describing itself two ways is this comparison. `skills` is the field to
    watch: Claude Code requires it and the Agent Plugins schema rejects it, so it
    belongs in exactly one of the two files and the closed-field check says which.
    """

    path = plugin_root / "plugin.json"
    manifest = _load_json(path, errors)
    if not manifest:
        return

    unknown = sorted(set(manifest) - AGENT_PLUGIN_FIELDS)
    if unknown:
        errors.append(f"{path}: fields outside the Agent Plugins schema: {unknown}")

    schema = manifest.get("$schema")
    if not isinstance(schema, str) or not AGENT_PLUGIN_SCHEMA.match(schema):
        errors.append(f"{path}: $schema must name an Agent Plugins manifest schema; found {schema!r}")
    else:
        declared_schemas.add(schema)

    for field in AGENT_PLUGIN_SHARED:
        if manifest.get(field) != claude_manifest.get(field):
            errors.append(f"{path}: {field} disagrees with .claude-plugin/plugin.json")

    # Clients installing from a directory show these, and a plugin whose only
    # trace of provenance is the marketplace it came from cannot be reported on.
    for field in ("homepage", "repository"):
        if manifest.get(field) != REPOSITORY_URL:
            errors.append(f"{path}: {field} must be {REPOSITORY_URL}")

    _validate_keywords(path, manifest, errors)

    extensions = manifest.get("extensions")
    if extensions is not None:
        if not isinstance(extensions, dict):
            errors.append(f"{path}: extensions must be an object keyed by namespace")
        else:
            for namespace, value in sorted(extensions.items()):
                if not EXTENSION_NAMESPACE.match(namespace):
                    errors.append(f"{path}: extension namespace {namespace!r} must be reverse-domain")
                if not isinstance(value, dict):
                    errors.append(f"{path}: extension {namespace!r} must hold an object")


def _validate_keywords(path: Path, manifest: dict[str, object], errors: list[str]) -> None:
    """The only field here nobody in this repository reads, and the one users search.

    Nothing installs differently for a missing `keywords`, which is exactly why
    it goes unwritten: the cost of omitting it lands on a stranger typing a term
    into a plugin directory, not on the build.
    """

    keywords = manifest.get("keywords")
    if not isinstance(keywords, list) or len(keywords) < MINIMUM_KEYWORDS:
        errors.append(f"{path}: keywords must list at least {MINIMUM_KEYWORDS} search terms")
        return

    name = manifest.get("name")
    for keyword in keywords:
        if not isinstance(keyword, str) or not KEBAB_CASE.match(keyword):
            errors.append(f"{path}: keyword {keyword!r} must be lowercase kebab-case")
        elif keyword == name:
            errors.append(f"{path}: keyword {keyword!r} restates the plugin name")
    if len(set(keywords)) != len(keywords):
        errors.append(f"{path}: keywords repeat a term")


def _validate_bookmark(name: str, entry: tuple[object, object], errors: list[str]) -> None:
    """A bookmark has no tree here, so its marketplace entry is all there is to check."""

    source, skills = entry
    if skills is not None:
        errors.append(f"{name} is a bookmark; which skills it carries is its owner's to declare")
    if not isinstance(source, dict):
        errors.append(f"{name} bookmark must carry a remote source; found {source!r}")
        return
    kind = source.get("source")
    if kind not in REMOTE_SOURCE_KINDS:
        expected = sorted(REMOTE_SOURCE_KINDS)
        errors.append(f"{name} bookmark source must be one of {expected}; found {kind!r}")
    url = source.get("url")
    if not isinstance(url, str) or not url.startswith("https://"):
        errors.append(f"{name} bookmark must be fetched over https; found {url!r}")
    sha = source.get("sha")
    if not isinstance(sha, str) or not COMMIT_SHA.match(sha):
        errors.append(f"{name} bookmark must pin a full commit sha; found {sha!r}")
    if kind == "git-subdir" and not source.get("path"):
        errors.append(f"{name} bookmark selects a subdirectory without naming one")


def _validate_skill(skill_path: Path, license_name: str, errors: list[str]) -> None:
    skill_file = skill_path / "SKILL.md"
    text = _read_text(skill_file, errors)
    metadata = _parse_frontmatter(text, skill_file, errors)
    expected = {
        "name": skill_path.name,
        "license": license_name,
    }
    for field, value in expected.items():
        if metadata.get(field) != value:
            errors.append(f"{skill_file}: {field} must be {value!r}")
    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append(f"{skill_file}: description must be nonempty")
    nested = metadata.get("metadata")
    if not isinstance(nested, dict) or nested.get("version") != VERSION:
        errors.append(f"{skill_file}: metadata.version must be {VERSION}")
    if len(text.splitlines()) >= 500:
        errors.append(f"{skill_file}: body must stay under 500 lines")

    agent_file = skill_path / "agents" / "openai.yaml"
    agent_text = _read_text(agent_file, errors)
    for phrase in ("interface:", "display_name:", "short_description:"):
        if phrase not in agent_text:
            errors.append(f"{agent_file}: missing {phrase}")

    for target in MARKDOWN_LINK.findall(_strip_fenced_blocks(text)):
        if target.startswith(("https://", "http://", "#")):
            continue
        relative_target = target.split("#", 1)[0]
        if not relative_target:
            continue
        candidate = (skill_path / relative_target).resolve()
        try:
            candidate.relative_to(skill_path.resolve())
        except ValueError:
            errors.append(f"{skill_file}: reference escapes the skill: {target}")
            continue
        if not candidate.is_file():
            errors.append(f"{skill_file}: missing reference target {target}")

    nested_skill_files = [path for path in skill_path.rglob("SKILL.md") if path != skill_file]
    if nested_skill_files:
        errors.append(f"{skill_path}: nested SKILL.md files are not publishable")

    _validate_runtime_text(skill_path, errors)


def _validate_runtime_text(root: Path, errors: list[str]) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        content = _read_text(path, errors)
        for forbidden in FORBIDDEN_RUNTIME_TEXT:
            if forbidden in content:
                errors.append(f"{path}: contains forbidden hardcode {forbidden!r}")
        for fragment, reason in NON_PORTABLE_TEXT:
            if fragment in content:
                errors.append(f"{path}: contains {reason} {fragment!r}")


def _strip_fenced_blocks(text: str) -> str:
    """Drop fenced code blocks so sample markup is not mistaken for a reference."""

    kept: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        stripped = line.lstrip()
        ticks = len(stripped) - len(stripped.lstrip("`"))
        if fence is None:
            if ticks >= 3:
                fence = "`" * ticks
                continue
            kept.append(line)
        elif ticks >= len(fence) and not stripped.strip("`"):
            fence = None
    return "\n".join(kept)


def _parse_frontmatter(
    text: str,
    path: Path,
    errors: list[str],
) -> dict[str, object]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        errors.append(f"{path}: missing opening frontmatter delimiter")
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        errors.append(f"{path}: missing closing frontmatter delimiter")
        return {}

    parsed: dict[str, object] = {}
    section: str | None = None
    for raw_line in lines[1:end]:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indentation = len(raw_line) - len(raw_line.lstrip(" "))
        if ":" not in raw_line:
            errors.append(f"{path}: unsupported frontmatter line {raw_line!r}")
            continue
        key, raw_value = raw_line.strip().split(":", 1)
        value = _unquote(raw_value.strip())
        if indentation == 0:
            if raw_value.strip():
                parsed[key] = value
                section = None
            else:
                parsed[key] = {}
                section = key
        elif indentation == 2 and section is not None:
            nested = parsed.get(section)
            if isinstance(nested, dict):
                nested[key] = value
        else:
            errors.append(f"{path}: unsupported frontmatter indentation")
    return parsed


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _load_json(path: Path, errors: list[str]) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        errors.append(f"{path}: cannot read JSON: {error}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path}: JSON root must be an object")
        return {}
    return value


def _read_text(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        errors.append(f"{path}: cannot read UTF-8 text: {error}")
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()
    errors = validate_repository(run_tests=not args.skip_tests)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print("repository validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
