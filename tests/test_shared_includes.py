"""Hold every skill's shared.json to what the skill actually uses.

A skill that declares an include list receives only those files from its plugin's
shared/. The list is hand-written, so it can fail in two directions, and both
are silent until someone runs the skill on its own: a module the scripts import
that the list forgot, which breaks the installed skill, and a file the list still
names after nothing uses it, which ships dead weight forever. Both are read off
the code here rather than trusted.
"""

from __future__ import annotations

import ast
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"
SYNC_SCRIPT = ROOT / "scripts" / "sync-shared.py"
# A license is vendored because the skill's own frontmatter declares one that
# requires it, not because any file names it.
LICENSE_PREFIX = "LICENSE"


def load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_shared_includes", SYNC_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SYNC = load_sync_module()


def skills_with_include_lists() -> list[Path]:
    return sorted(path.parent for path in PLUGINS.glob(f"*/skills/*/{SYNC.SKILL_MANIFEST}"))


def plugin_shared(skill: Path) -> Path:
    return skill.parent.parent / SYNC.VENDORED_DIRNAME


def included_files(skill: Path) -> set[Path]:
    """Return the shared/ files, relative to it, that the skill's list vendors."""

    source = plugin_shared(skill)
    include = SYNC.skill_include(skill, source)
    return SYNC._expected_files(SYNC.Pair(source, skill / SYNC.VENDORED_DIRNAME, include))


def instruction_text(skill: Path) -> str:
    """What the agent reads: SKILL.md and everything under references/."""

    parts = [(skill / "SKILL.md").read_text(encoding="utf-8")]
    references = skill / "references"
    if references.is_dir():
        parts.extend(path.read_text(encoding="utf-8") for path in sorted(references.rglob("*.md")))
    return "\n".join(parts)


def resolve_module(dotted: str, roots: list[Path]) -> list[Path]:
    """Return the files importing `dotted` executes: each package __init__, then the module."""

    parts = dotted.split(".")
    for root in roots:
        files: list[Path] = []
        for depth in range(1, len(parts) + 1):
            candidate = root.joinpath(*parts[:depth])
            if (candidate / "__init__.py").is_file():
                files.append(candidate / "__init__.py")
            elif depth == len(parts) and candidate.with_suffix(".py").is_file():
                files.append(candidate.with_suffix(".py"))
            else:
                break
        if len(files) == len(parts):
            return files
    return []


def imported_files(path: Path, roots: list[Path]) -> set[Path]:
    """Every local file one module's import statements reach, without following them."""

    found: set[Path] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.update(resolve_module(alias.name, roots))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = path.parent
                for _ in range(node.level - 1):
                    base = base.parent
                package_roots = [base]
                stem = node.module or ""
            else:
                package_roots = roots
                stem = node.module or ""
            if stem:
                found.update(resolve_module(stem, package_roots))
            for alias in node.names:
                # `from astro import profiles` imports a submodule, not an attribute.
                submodule = f"{stem}.{alias.name}" if stem else alias.name
                found.update(resolve_module(submodule, package_roots))
    return found


def import_closure(skill: Path) -> set[Path]:
    """Every shared/ Python file the skill's scripts, or a shared script its SKILL.md runs, load."""

    shared = plugin_shared(skill)
    scripts = skill / "scripts"
    instructions = instruction_text(skill)
    pending = sorted(scripts.glob("*.py")) if scripts.is_dir() else []
    pending += [
        path
        for path in sorted(shared.rglob("*.py"))
        if f"shared/{path.relative_to(shared).as_posix()}" in instructions
    ]
    seen: set[Path] = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        roots = [shared] if current.is_relative_to(shared) else [scripts, shared]
        pending.extend(imported_files(current, roots) - seen)
    return {path.relative_to(shared) for path in seen if path.is_relative_to(shared)}


class SharedIncludeListTests(unittest.TestCase):
    def test_some_skill_declares_a_list(self) -> None:
        """A check over an empty set proves nothing."""

        self.assertTrue(skills_with_include_lists())

    def test_every_imported_shared_module_is_included(self) -> None:
        for skill in skills_with_include_lists():
            included = included_files(skill)
            for relative in sorted(import_closure(skill)):
                with self.subTest(skill=skill.name, module=relative.as_posix()):
                    self.assertIn(
                        relative,
                        included,
                        f"{skill.name} imports shared/{relative.as_posix()} but its shared.json omits it",
                    )

    def test_every_included_module_is_imported_or_run(self) -> None:
        for skill in skills_with_include_lists():
            used = import_closure(skill)
            for relative in sorted(included_files(skill)):
                if relative.suffix != ".py":
                    continue
                with self.subTest(skill=skill.name, module=relative.as_posix()):
                    self.assertIn(
                        relative,
                        used,
                        f"{skill.name} vendors shared/{relative.as_posix()}, which nothing it runs imports",
                    )

    def test_every_included_data_file_is_named_by_something_the_skill_ships(self) -> None:
        for skill in skills_with_include_lists():
            shared = plugin_shared(skill)
            included = included_files(skill)
            own = [skill / "SKILL.md"]
            for directory, pattern in (("references", "*"), ("scripts", "*.py")):
                if (skill / directory).is_dir():
                    own += sorted((skill / directory).rglob(pattern))
            texts = {path: path.read_text(encoding="utf-8") for path in own if path.is_file()}
            for relative in included:
                texts[shared / relative] = (shared / relative).read_text(encoding="utf-8", errors="ignore")
            for relative in sorted(included):
                if relative.suffix == ".py" or relative.name.startswith(LICENSE_PREFIX):
                    continue
                namers = [
                    path
                    for path, text in texts.items()
                    if path != shared / relative and relative.name in text
                ]
                with self.subTest(skill=skill.name, file=relative.as_posix()):
                    self.assertTrue(
                        namers,
                        f"{skill.name} vendors shared/{relative.as_posix()}, which nothing it ships names",
                    )

    def test_a_plugin_license_travels_with_every_skill(self) -> None:
        for skill in skills_with_include_lists():
            shared = plugin_shared(skill)
            licenses = {
                path.relative_to(shared) for path in shared.glob(f"{LICENSE_PREFIX}*") if path.is_file()
            }
            with self.subTest(skill=skill.name):
                self.assertLessEqual(licenses, included_files(skill))

    def test_every_script_starts_when_its_skill_is_copied_out_alone(self) -> None:
        """Import-time data reads too: a rules table loaded at import fails here."""

        for skill in skills_with_include_lists():
            scripts = skill / "scripts"
            if not scripts.is_dir():
                continue
            with tempfile.TemporaryDirectory() as directory:
                copy = Path(directory) / skill.name
                shutil.copytree(skill, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                for script in sorted((copy / "scripts").glob("*.py")):
                    if "__main__" in script.read_text(encoding="utf-8"):
                        arguments = [str(script), "--help"]
                    else:
                        path = [str(copy / "scripts"), str(copy / "shared")]
                        arguments = ["-c", f"import sys; sys.path[:0] = {path!r}; import {script.stem}"]
                    result = subprocess.run(
                        [sys.executable, "-E", "-s", *arguments],
                        cwd=copy,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    with self.subTest(skill=skill.name, script=script.name):
                        self.assertEqual(result.returncode, 0, result.stderr)


class ImportGraphTests(unittest.TestCase):
    """The graph reader above is what the list checks rest on, so it is tested too."""

    def test_it_follows_absolute_relative_and_submodule_imports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "pkg"
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "a.py").write_text("from .b import thing\n", encoding="utf-8")
            (package / "b.py").write_text("thing = 1\n", encoding="utf-8")
            (package / "c.py").write_text("", encoding="utf-8")
            entry = root / "entry.py"
            entry.write_text("import json\nfrom pkg import c\nfrom pkg.a import thing\n", encoding="utf-8")

            direct = imported_files(entry, [root])
            relative = imported_files(package / "a.py", [root])

        self.assertEqual(direct, {package / "__init__.py", package / "a.py", package / "c.py"})
        self.assertEqual(relative, {package / "b.py"})


if __name__ == "__main__":
    unittest.main()
