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
MARKETPLACE_NAME = "misoto22"
VERSION = "0.8.1"

# The published surface, asserted exactly: a plugin or skill that appears on disk
# without being added here is unregistered somewhere, and one listed here without
# appearing on disk has been dropped.
PUBLISHED = {
    "astrology": ["synastry"],
    "dev": ["cleanup", "ship", "sync"],
    "docs": ["readme"],
    "writing": ["email", "tempering"],
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
    "obsidian",
    "warp",
}
# The sha is the whole guarantee. An entry pinned to a branch installs whatever
# that repository holds at install time, which hands its owner — or anyone who
# takes it over — a write path into every agent that trusts this marketplace.
COMMIT_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
REMOTE_SOURCE_KINDS = {"git-subdir", "url"}

# One entry installs the rest, by depending on every plugin above. It carries no
# skills, so it sits outside plugins/ where the packager, list-skills.sh, and the
# per-skill install routes cannot mistake it for one. Its dependency list is
# asserted against both registries: a bookmark added without a matching entry
# here would be a plugin the one-command install silently skips.
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


def validate_repository(*, run_tests: bool) -> list[str]:
    errors: list[str] = []
    marketplace = _load_json(ROOT / ".claude-plugin" / "marketplace.json", errors)
    root_readme = _read_text(ROOT / "README.md", errors)

    found_plugins = sorted(
        path.parent.parent.name for path in PLUGINS_ROOT.glob("*/.claude-plugin/plugin.json")
    )
    if found_plugins != sorted(PUBLISHED):
        errors.append(f"published plugins must be {sorted(PUBLISHED)}; found {found_plugins}")

    if marketplace.get("name") != MARKETPLACE_NAME:
        errors.append(f"marketplace name must be {MARKETPLACE_NAME!r}")
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
    _validate_bundle(registered.get(BUNDLE), errors)
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

    for plugin_name, expected_skills in sorted(PUBLISHED.items()):
        plugin_root = PLUGINS_ROOT / plugin_name
        skills_root = plugin_root / "skills"
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
            ("license", "MIT"),
        ):
            if plugin.get(field) != expected:
                errors.append(f"{plugin_name} plugin {field} must be {expected!r}")
        author = plugin.get("author")
        if not isinstance(author, dict) or author.get("name") != "skills contributors":
            errors.append(f"{plugin_name} plugin author must identify 'skills contributors'")

        skills_readme = _read_text(skills_root / "README.md", errors)
        for name in names:
            if f"plugins/{plugin_name}/skills/{name}/SKILL.md" not in root_readme:
                errors.append(f"README.md does not register {plugin_name}/{name}")
            if f"{name}/SKILL.md" not in skills_readme:
                errors.append(f"{plugin_name} skills/README.md does not register {name}")

        # The registries say every published skill is listed. This says every
        # listing is a published skill, which is what a retirement gets wrong.
        for reference in SKILL_REFERENCE.findall(skills_readme):
            if not (skills_root / reference).is_file():
                errors.append(f"{plugin_name} skills/README.md lists {reference}, which is gone")

        for skill_path in skill_paths:
            _validate_skill(skill_path, errors)

        # shared/ ships inside every published skill, so it is held to the same
        # runtime-neutrality rule as the skills that read it.
        _validate_runtime_text(plugin_root / "shared", errors)

    for reference in PUBLISHED_REFERENCE.findall(root_readme):
        if not (ROOT / reference).is_file():
            errors.append(f"README.md links {reference}, which does not exist")

    for retired_root in RETIRED_ROOTS:
        for skill_file in sorted((ROOT / retired_root).rglob("SKILL.md")):
            relative = skill_file.relative_to(ROOT).as_posix()
            if relative in root_readme:
                errors.append(f"README.md lists {relative}, which is not published")

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


def _validate_bundle(entry: tuple[object, object] | None, errors: list[str]) -> None:
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
        ("license", "MIT"),
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
    expected_dependencies = sorted(f"{name}@{MARKETPLACE_NAME}" for name in (*PUBLISHED, *BOOKMARKED))
    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, list) or sorted(dependencies) != expected_dependencies:
        errors.append(f"{BUNDLE} bundle must depend on exactly {expected_dependencies}")


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


def _validate_skill(skill_path: Path, errors: list[str]) -> None:
    skill_file = skill_path / "SKILL.md"
    text = _read_text(skill_file, errors)
    metadata = _parse_frontmatter(text, skill_file, errors)
    expected = {
        "name": skill_path.name,
        "license": "MIT",
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
