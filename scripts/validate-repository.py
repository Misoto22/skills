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
VERSION = "0.7.0"

# The published surface, asserted exactly: a plugin or skill that appears on disk
# without being added here is unregistered somewhere, and one listed here without
# appearing on disk has been dropped.
PUBLISHED = {
    "dev": ["cleanup", "ship", "sync"],
    "docs": ["readme"],
    "writing": ["email", "tempering"],
}
TEXT_SUFFIXES = {".md", ".json", ".py", ".txt", ".yaml", ".yml", ".sh"}
FORBIDDEN_RUNTIME_TEXT = (
    "/Users/",
    "/home/",
    "smtp.gmail.com",
    "provider-specific mail command",
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

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
    if not isinstance(metadata, dict) or metadata.get("pluginRoot") != "./plugins":
        errors.append("marketplace pluginRoot must be './plugins'")
    entries = marketplace.get("plugins")
    entries = entries if isinstance(entries, list) else []
    registered = {entry.get("name"): entry.get("source") for entry in entries if isinstance(entry, dict)}
    expected_sources = {name: f"./plugins/{name}" for name in PUBLISHED}
    if registered != expected_sources:
        errors.append(f"marketplace must register exactly {expected_sources}; found {registered}")

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

        for skill_path in skill_paths:
            _validate_skill(skill_path, errors)

        # shared/ ships inside every published skill, so it is held to the same
        # runtime-neutrality rule as the skills that read it.
        _validate_runtime_text(plugin_root / "shared", errors)

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
