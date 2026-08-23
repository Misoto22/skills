from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"
PLUGIN = PLUGINS / "writing"
SKILLS = PLUGIN / "skills"
DOCS_PLUGIN = PLUGINS / "docs"
README_PATH = ROOT / "README.md"
# Every root README is a registry the scaffold writes to, so every one of them has
# to be snapshotted and restored by the round-trip tests below. Naming only the
# English one leaves a translation holding a scaffolded PLACEHOLDER afterwards.
ROOT_READMES = [path.name for path in sorted(ROOT.glob("README*.md"))]
# Everything the scaffold writes to and the retirement has to put back. Named
# once: three tests asserted against their own copy of this list, and a registry
# added to one of them was silently unchecked by the other two.
REGISTRIES = [
    ".claude-plugin/marketplace.json",
    "bundle/.claude-plugin/plugin.json",
    "scripts/validate-repository.py",
    ".version-bump.json",
    "skills.sh.json",
    "registry.json",
    "i18n/zh.json",
    *ROOT_READMES,
]
SKILLS_README_PATH = SKILLS / "README.md"
PLUGIN_PATH = PLUGIN / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = ROOT / ".claude-plugin" / "marketplace.json"
LINK_SCRIPT = ROOT / "scripts" / "link-skills.sh"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
RELEASE_HEADING = re.compile(r"^## (\d+\.\d+\.\d+) — \d{4}-\d{2}-\d{2}$")


def declared_version() -> str:
    """Read the version the validator gates every manifest against."""

    text = (ROOT / "scripts" / "validate-repository.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION = "([^"]+)"', text, re.MULTILINE)
    assert match, "validate-repository.py declares no VERSION"
    return match.group(1)


def marketplace_name() -> str:
    """Read the install suffix from the manifest that declares it.

    Restating `misoto22` here would put the name back in a seventh file, which
    is the thing the scripts under test stopped doing.
    """

    return json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))["name"]


def bumped_version(pin: dict) -> str:
    """Return a probe value of the shape this pin declares, different from its current one.

    Pins no longer all take a semver: a runtime is `3.13` or `22`, and the model
    an evaluation bills against is a name. A test that bumped everything to
    9.9.9 would be asserting the old, narrower rule.
    """

    pattern = pin.get("version_pattern", r"\d+\.\d+\.\d+")
    for candidate in ("9.9.9", "9.9", "9", f"{pin['version']}-probe", "probe-9"):
        if candidate != pin["version"] and re.fullmatch(pattern, candidate):
            return candidate
    raise AssertionError(f"no probe version matches {pin['id']}'s shape {pattern!r}")


def published_skills() -> dict[str, list[str]]:
    """Return {plugin: [skill, ...]} from the tree, sorted the way the registries are."""

    found: dict[str, list[str]] = {}
    for skill_file in sorted(PLUGINS.glob("*/skills/*/SKILL.md")):
        found.setdefault(skill_file.parent.parent.parent.name, []).append(skill_file.parent.name)
    return {plugin: sorted(skills) for plugin, skills in sorted(found.items())}


def bookmarked_plugins() -> set[str]:
    """Read the bookmarks, which live in the validator beside the published list."""

    text = (ROOT / "scripts" / "validate-repository.py").read_text(encoding="utf-8")
    match = re.search(r"^BOOKMARKED = \{(.*?)\n\}", text, re.MULTILINE | re.DOTALL)
    assert match, "validate-repository.py declares no BOOKMARKED"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def declared_bundle() -> str:
    """Read the name of the entry that installs every other entry."""

    text = (ROOT / "scripts" / "validate-repository.py").read_text(encoding="utf-8")
    match = re.search(r'^BUNDLE = "([^"]+)"', text, re.MULTILINE)
    assert match, "validate-repository.py declares no BUNDLE"
    return match.group(1)


def copy_repository_fixture(destination: Path) -> Path:
    """Copy the checkout without VCS, generated state, or anyone else's checkout."""

    copied = destination / "repository"
    shutil.copytree(ROOT, copied, ignore=_fixture_ignore)
    return copied


def _fixture_ignore(directory: str, names: list[str]) -> set[str]:
    """Drop generated state, and drop a nested checkout whole.

    `ignore_patterns` stripped the `.git` marker but kept the tree under it, so a
    `git worktree` anywhere in the checkout arrived in the fixture as a second
    copy of every manifest with nothing left to identify it. A fixture of "this
    repository" must not contain someone's other one.
    """

    dropped = {name for name in names if name in _FIXTURE_EXCLUDED or name.endswith(".pyc")}
    root = Path(directory)
    for name in names:
        if name in dropped or Path(directory, name).is_symlink() or not Path(directory, name).is_dir():
            continue
        if (root / name / ".git").exists() and root != ROOT.parent:
            dropped.add(name)
    return dropped


_FIXTURE_EXCLUDED = frozenset({".git", ".claude", ".superpowers", "__pycache__", ".coverage"})


@contextlib.contextmanager
def repository_copy() -> Iterator[Path]:
    """Yield a throwaway checkout for a test that has to edit one.

    Every test below that rewrites a registry, drops a registration, or retires
    a real skill used to do it to this checkout and put it back in a `finally`.
    That works until the run is interrupted — Ctrl-C, a killed runner, an
    assertion that raises somewhere unexpected — and then the tree is left
    half-edited, and the suite cannot run two of these at once either. A copy
    costs about 0.15s and removes both problems.
    """

    with tempfile.TemporaryDirectory() as temporary:
        yield copy_repository_fixture(Path(temporary))


class RepositoryContractTests(unittest.TestCase):
    def test_only_published_tree_is_in_plugin_manifest(self) -> None:
        plugin = json.loads(PLUGIN_PATH.read_text(encoding="utf-8"))

        # Derived from the tree. Written out, this list is a fourth registry —
        # one the scaffold does not know about, so adding a writing skill would
        # fail here rather than anywhere that names it.
        self.assertEqual(
            plugin["skills"],
            [f"./skills/{skill}" for skill in published_skills()[PLUGIN.name]],
        )
        self.assertEqual(plugin["author"]["name"], "skills contributors")
        self.assertNotIn("drafts", json.dumps(plugin))
        self.assertNotIn("deprecated", json.dumps(plugin))

    def test_marketplace_registers_the_writing_plugin(self) -> None:
        marketplace = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))

        # Held to a shape rather than to a literal: this file is where the name
        # is declared, so asserting it equals itself proves nothing, and the
        # claude.ai marketplace sync is what actually rejects a bad one.
        self.assertRegex(marketplace["name"], r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")
        # Claude Code resolves a source against the repository root and the skills
        # CLI prepends pluginRoot to it, so setting pluginRoot breaks one of them
        # whichever way the sources are then written.
        self.assertNotIn("pluginRoot", marketplace["metadata"])
        # Bookmarks and the bundle are registered here too. Neither has a tree
        # under plugins/, so only the entries backed by one are matched to it.
        untreed = bookmarked_plugins() | {declared_bundle()}
        registered = {
            entry["name"]: entry for entry in marketplace["plugins"] if entry["name"] not in untreed
        }
        on_disk = {path.parent.parent.name for path in PLUGINS.glob("*/.claude-plugin/plugin.json")}
        self.assertEqual(set(registered), on_disk)
        for name, entry in registered.items():
            self.assertEqual(entry["source"], f"./plugins/{name}")
            skills = sorted(path.parent.name for path in (PLUGINS / name / "skills").glob("*/SKILL.md"))
            self.assertEqual(entry["skills"], [f"./skills/{skill}" for skill in skills])

    def test_the_bundle_installs_every_other_entry(self) -> None:
        """One command is the claim; an entry left out of it is the claim breaking."""

        marketplace = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))
        bundle = declared_bundle()
        manifest = json.loads((ROOT / "bundle" / ".claude-plugin" / "plugin.json").read_text())

        registered = {entry["name"] for entry in marketplace["plugins"]}
        suffix = marketplace_name()
        self.assertIn(bundle, registered)
        self.assertEqual(
            sorted(manifest["dependencies"]),
            sorted(f"{name}@{suffix}" for name in registered - {bundle}),
        )
        # Depending on itself is a cycle, and carrying skills would make the
        # bundle a fourth plugin to maintain rather than a way to install three.
        self.assertNotIn(f"{bundle}@{suffix}", manifest["dependencies"])
        self.assertNotIn("skills", manifest)
        self.assertFalse((PLUGINS / bundle).exists())

    def test_every_entry_but_the_bundle_declares_a_category(self) -> None:
        """A category of one is what an invented word gets you in the browser."""

        validator = (ROOT / "scripts" / "validate-repository.py").read_text(encoding="utf-8")
        block = re.search(r"^CATEGORIES = \{(.*?)\n\}", validator, re.MULTILINE | re.DOTALL)
        vocabulary = set(re.findall(r'"([^"]+)"', block.group(1)))
        marketplace = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))
        bundle = declared_bundle()

        self.assertTrue(vocabulary)
        for entry in marketplace["plugins"]:
            if entry["name"] == bundle:
                # An entry point to the others, so it belongs under none of them.
                self.assertNotIn("category", entry)
                continue
            self.assertIn(entry.get("category"), vocabulary, entry["name"])

    def test_new_and_removed_plugins_move_the_bundle_with_them(self) -> None:
        """The scaffold and the retirement own this, or the next plugin is missed."""

        scaffold = (ROOT / "scripts" / "new-skill.py").read_text(encoding="utf-8")
        retire = (ROOT / "scripts" / "remove-skill.py").read_text(encoding="utf-8")

        self.assertIn("_register_bundle(args.plugin, created)", scaffold)
        self.assertIn("_unregister_bundle(args.plugin, touched)", retire)

    def test_every_bookmark_pins_a_commit(self) -> None:
        """An unpinned bookmark installs whatever its owner holds at install time."""

        marketplace = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))
        bookmarked = bookmarked_plugins()
        entries = {entry["name"]: entry for entry in marketplace["plugins"] if entry["name"] in bookmarked}

        self.assertEqual(set(entries), bookmarked)
        for name, entry in sorted(entries.items()):
            source = entry["source"]
            self.assertIn(source["source"], {"git-subdir", "url"}, name)
            self.assertTrue(source["url"].startswith("https://"), name)
            self.assertRegex(source["sha"], r"\A[0-9a-f]{40}\Z", name)
            # Which skills a bookmark carries is its owner's to change, and a
            # stale copy of that list here would advertise skills it dropped.
            self.assertNotIn("skills", entry, name)
        for name in bookmarked:
            self.assertFalse((PLUGINS / name).exists(), f"{name} is bookmarked and vendored")

    def test_every_published_skill_is_registered(self) -> None:
        """Every source of truth agrees. The canonical list lives in the validator."""

        validator = (ROOT / "scripts" / "validate-repository.py").read_text(encoding="utf-8")
        block = re.search(r"PUBLISHED = \{(.*?)\n\}", validator, re.DOTALL).group(1)
        published = {
            name: re.findall(r'"([^"]+)"', skills)
            for name, skills in re.findall(r'"([^"]+)": \[([^\]]*)\]', block)
        }
        self.assertTrue(published)
        root_readme = README_PATH.read_text(encoding="utf-8")

        found = sorted(path.parent.parent.name for path in PLUGINS.glob("*/.claude-plugin/plugin.json"))
        self.assertEqual(found, sorted(published))

        for plugin, expected in published.items():
            skills = PLUGINS / plugin / "skills"
            names = sorted(path.parent.name for path in skills.glob("*/SKILL.md"))
            self.assertEqual(names, expected)

            skills_readme = (skills / "README.md").read_text(encoding="utf-8")
            for name in names:
                self.assertIn(f"plugins/{plugin}/skills/{name}/SKILL.md", root_readme)
                self.assertIn(f"{name}/SKILL.md", skills_readme)
                self.assertIn(f"/{plugin}:{name}`", root_readme)

    def test_every_translated_readme_registers_every_skill(self) -> None:
        """A translation nothing checks goes stale on the next skill added, silently."""

        translations = sorted(path for path in ROOT.glob("README*.md") if path.name != "README.md")
        self.assertTrue(translations, "no translated README to hold to the registry")

        for path in translations:
            text = path.read_text(encoding="utf-8")
            for skill_file in PLUGINS.glob("*/skills/*/SKILL.md"):
                skill = skill_file.parent.name
                plugin = skill_file.parent.parent.parent.name
                self.assertIn(f"plugins/{plugin}/skills/{skill}/SKILL.md", text, path.name)
                self.assertIn(f"/{plugin}:{skill}`", text, path.name)

    def test_the_validator_rejects_a_translation_that_dropped_a_skill(self) -> None:
        """The check above only means something if the validator fails without it."""

        skill_file = sorted(PLUGINS.glob("*/skills/*/SKILL.md"))[0]
        registered = (
            f"plugins/{skill_file.parent.parent.parent.name}/skills/{skill_file.parent.name}/SKILL.md"
        )
        with repository_copy() as copied:
            translation = next(path for path in sorted(copied.glob("README*.md")) if path.name != "README.md")
            # Drop one skill's registration, exactly as forgetting to translate it would.
            text = translation.read_text(encoding="utf-8")
            translation.write_text(text.replace(registered, "", 1), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "scripts/validate-repository.py", "--skip-tests"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0, "a translation missing a skill validated")
        self.assertIn(translation.name, result.stderr)
        self.assertIn("does not register", result.stderr)

    def test_every_plugin_ships_both_manifests_and_they_agree(self) -> None:
        """Claude Code reads one file, every Agent Plugins client reads the other."""

        schema = re.compile(r"\Ahttps://agent-plugins\.org/schemas/\d+\.\d+\.\d+/plugin\.schema\.json\Z")
        claude = sorted(path.parent.parent.name for path in PLUGINS.glob("*/.claude-plugin/plugin.json"))
        portable = sorted(path.parent.name for path in PLUGINS.glob("*/plugin.json"))
        self.assertEqual(claude, portable, "a plugin carries one manifest and not the other")
        self.assertTrue(portable)

        declared = set()
        for name in portable:
            manifest = json.loads((PLUGINS / name / "plugin.json").read_text(encoding="utf-8"))
            beside = json.loads(
                (PLUGINS / name / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
            )

            self.assertRegex(manifest["$schema"], schema, name)
            declared.add(manifest["$schema"])
            # Nothing here reads keywords, so nothing but this notices them going
            # missing — and the cost lands on a stranger searching a directory.
            self.assertGreaterEqual(len(manifest["keywords"]), 3, name)
            self.assertNotIn(name, manifest["keywords"], f"{name}: keyword restates the plugin name")
            for keyword in manifest["keywords"]:
                self.assertRegex(keyword, r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z", f"{name}: {keyword}")
            for field in ("name", "version", "description", "license", "author"):
                self.assertEqual(manifest[field], beside[field], f"{name}: {field}")
            # The schema is closed, and both of these are outside it: the skills
            # tree is discovered from skills/, and dependencies have no spec.
            self.assertNotIn("skills", manifest, name)
            self.assertNotIn("dependencies", manifest, name)
        self.assertEqual(len(declared), 1, f"plugins target more than one schema: {sorted(declared)}")

    def test_the_validator_rejects_a_portable_manifest_that_drifted(self) -> None:
        """The agreement above only means something if disagreeing fails the build."""

        with repository_copy() as copied:
            manifest = copied / "plugins" / "docs" / "plugin.json"
            document = json.loads(manifest.read_text(encoding="utf-8"))
            for field, value, expected in (
                ("description", "Something else entirely.", "description disagrees"),
                ("skills", ["./skills/readme"], "outside the Agent Plugins schema"),
                ("$schema", "https://example.com/plugin.schema.json", "$schema must name"),
                ("keywords", ["only-one"], "at least 3 search terms"),
                ("keywords", ["Readme", "docs", "writing"], "must be lowercase kebab-case"),
                ("keywords", ["docs", "readme", "writing"], "restates the plugin name"),
                ("keywords", ["readme", "readme", "writing"], "keywords repeat a term"),
                ("extensions", {"codex": {}}, "must be reverse-domain"),
                ("extensions", {"com.openai.codex": []}, "must hold an object"),
                ("extensions", ["com.openai.codex"], "extensions must be an object"),
            ):
                manifest.write_text(json.dumps({**document, field: value}, indent=2) + "\n")
                result = subprocess.run(
                    [sys.executable, "scripts/validate-repository.py", "--skip-tests"],
                    cwd=copied,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0, field)
                self.assertIn(expected, result.stderr, f"{field} was not the rule that fired")

    def test_validator_rejects_astrology_license_downgrades(self) -> None:
        """MIT in either astrology metadata layer must not silently weaken the plugin license."""

        with tempfile.TemporaryDirectory() as temporary:
            copied = copy_repository_fixture(Path(temporary))
            cases = (
                (
                    copied / "plugins" / "astrology" / ".claude-plugin" / "plugin.json",
                    "plugin license must be 'AGPL-3.0-or-later'",
                ),
                (
                    copied / "plugins" / "astrology" / "skills" / "synastry" / "SKILL.md",
                    "license must be 'AGPL-3.0-or-later'",
                ),
            )
            for target, expected in cases:
                with self.subTest(target=target.relative_to(copied)):
                    original = target.read_bytes()
                    try:
                        target.write_text(
                            original.decode("utf-8").replace("AGPL-3.0-or-later", "MIT", 1),
                            encoding="utf-8",
                        )
                        result = subprocess.run(
                            [sys.executable, "scripts/validate-repository.py", "--skip-tests"],
                            cwd=copied,
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                    finally:
                        target.write_bytes(original)

                    self.assertNotEqual(result.returncode, 0, str(target))
                    self.assertIn(expected, result.stderr)

    def test_verify_install_rejects_a_half_installed_plugin(self) -> None:
        """A plugin root carrying one manifest and not the other is half a plugin."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dropped = root / "dropped"
            shutil.copytree(DOCS_PLUGIN, dropped)
            (dropped / "plugin.json").unlink()

            drifted = root / "drifted"
            shutil.copytree(DOCS_PLUGIN, drifted)
            manifest = drifted / "plugin.json"
            document = json.loads(manifest.read_text(encoding="utf-8"))
            manifest.write_text(json.dumps({**document, "version": "9.9.9"}, indent=2) + "\n")

            # Two of the four routes ship bare skills and no plugin root at all.
            bare = root / "bare"
            shutil.copytree(DOCS_PLUGIN / "skills" / "readme", bare / "readme")

            for target, expected in (
                (dropped, "dropped the Agent Plugins manifest"),
                (drifted, "disagree on name or version"),
            ):
                result = subprocess.run(
                    [sys.executable, "scripts/verify-install.py", str(target)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0, str(target))
                self.assertIn(expected, result.stderr)

            subprocess.run(
                [sys.executable, "scripts/verify-install.py", str(bare)],
                cwd=ROOT,
                check=True,
                capture_output=True,
            )

    def test_the_validator_resolves_every_relative_readme_link(self) -> None:
        """Links between the registry links and the skill links had no owner."""

        with repository_copy() as copied:
            readme = copied / README_PATH.name
            readme.write_bytes(readme.read_bytes() + b"\nSee [the handbook](docs/no-such-file.md).\n")
            result = subprocess.run(
                [sys.executable, "scripts/validate-repository.py", "--skip-tests"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("docs/no-such-file.md, which does not resolve", result.stderr)

    def test_every_readme_states_a_count_the_tree_agrees_with(self) -> None:
        """Both READMEs said "twelve skills" for two releases, with CI green."""

        validator = (ROOT / "scripts" / "validate-repository.py").read_text(encoding="utf-8")
        self.assertIn("STATED_COUNTS", validator)

        for path in sorted(ROOT.glob("README*.md")):
            self.assertIn(
                f'"{path.name}"',
                validator,
                f"{path.name} has no entry in STATED_COUNTS, so its count is unchecked",
            )

    def test_the_validator_rejects_a_readme_whose_count_went_stale(self) -> None:
        """The registration above only means something if a wrong count fails."""

        with tempfile.TemporaryDirectory() as temporary:
            copied = copy_repository_fixture(Path(temporary))
            english = copied / "README.md"
            text = english.read_text(encoding="utf-8")
            match = re.search(r"(?m)^([A-Za-z-]+) skills in ([A-Za-z-]+) plugins\b", text)
            self.assertIsNotNone(match, "README.md states no count for the validator to hold")

            for replacement, expected in (
                (f"Twelve skills in {match.group(2)} plugins", "skills"),
                (f"{match.group(1)} skills in nine plugins", "plugins"),
                ("A pile of skills, in some plugins", "states no published count"),
            ):
                english.write_text(text.replace(match.group(0), replacement, 1), encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, "scripts/validate-repository.py", "--skip-tests"],
                    cwd=copied,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0, replacement)
                self.assertIn("README.md", result.stderr)
                self.assertIn(expected, result.stderr, replacement)

    def test_the_scaffold_and_the_retirement_move_the_stated_count(self) -> None:
        """A check the tooling cannot satisfy is a chore, not a guard."""

        with tempfile.TemporaryDirectory() as temporary:
            copied = copy_repository_fixture(Path(temporary))
            readmes = {path.name: path.read_bytes() for path in sorted(copied.glob("README*.md"))}
            self.assertTrue(readmes)

            self._run_in(copied, "scripts/new-skill.py", "countprobe", "probe")
            for name in readmes:
                self.assertNotEqual((copied / name).read_bytes(), readmes[name], f"{name} kept its old count")

            self._run_in(copied, "scripts/remove-skill.py", "countprobe", "probe", "--delete")
            for name, content in readmes.items():
                self.assertEqual((copied / name).read_bytes(), content, name)

    def test_every_shipped_script_is_named_by_a_test(self) -> None:
        """AGENTS.md has always required this, and only coverage ever noticed."""

        # Assembled rather than written out. This file lives under tests/, and
        # the rule is that the module's name appears somewhere there — so a
        # literal here would satisfy the very check being probed.
        stem = "unreferenced" + "_probe_module"

        with tempfile.TemporaryDirectory() as temporary:
            copied = copy_repository_fixture(Path(temporary))
            scripts = copied / "plugins" / "docs" / "skills" / "readme" / "scripts"
            scripts.mkdir(parents=True, exist_ok=True)
            (scripts / f"{stem}.py").write_text("def probe():\n    return None\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "scripts/validate-repository.py", "--skip-tests"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(stem, result.stderr)
        self.assertIn("requires unit tests", result.stderr)

    def test_the_coverage_floor_is_written_down_once(self) -> None:
        """CONTRIBUTING said 75% while .coveragerc said 82, and nothing compared them."""

        floor = re.search(r"(?m)^fail_under = (\d+)$", (ROOT / ".coveragerc").read_text(encoding="utf-8"))
        self.assertIsNotNone(floor)

        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn(".coveragerc", contributing)
        self.assertNotRegex(
            contributing,
            r"floors? at \d+%",
            "CONTRIBUTING restates the coverage floor; point at .coveragerc instead",
        )

    def test_docs_plugin_declares_the_readme_skill(self) -> None:
        plugin = json.loads((DOCS_PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))

        self.assertEqual(plugin["name"], "docs")
        self.assertEqual(
            plugin["skills"],
            [f"./skills/{skill}" for skill in published_skills()["docs"]],
        )
        self.assertEqual(plugin["version"], declared_version())
        self.assertFalse((DOCS_PLUGIN / "shared").exists(), "docs has one skill and needs no shared/")

    def test_link_script_never_recursively_deletes_targets(self) -> None:
        script = LINK_SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn("rm -rf", script)
        self.assertIn("conflict", script.lower())

    def test_list_script_prints_only_published_skills(self) -> None:
        result = subprocess.run(
            ["bash", "scripts/list-skills.sh"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        expected = sorted(
            f"{path.relative_to(ROOT).as_posix()}\n" for path in PLUGINS.glob("*/skills/*/SKILL.md")
        )
        self.assertEqual(result.stdout, "".join(expected))

    def test_link_script_creates_editable_links_in_isolated_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = {
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin",
                "HOME": str(root / "home"),
                "AGENTS_SKILLS_DIR": str(root / "agents"),
                "CLAUDE_SKILLS_DIR": str(root / "claude"),
            }
            subprocess.run(
                ["bash", "scripts/link-skills.sh"],
                cwd=ROOT,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertEqual((root / "agents" / "email").resolve(), (SKILLS / "email").resolve())
            self.assertEqual((root / "claude" / "email").resolve(), (SKILLS / "email").resolve())

    def test_link_script_preserves_real_directory_on_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            conflict = root / "agents" / "email"
            conflict.mkdir(parents=True)
            marker = conflict / "keep.txt"
            marker.write_text("keep\n", encoding="utf-8")
            environment = {
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin",
                "HOME": str(root / "home"),
                "AGENTS_SKILLS_DIR": str(root / "agents"),
                "CLAUDE_SKILLS_DIR": str(root / "claude"),
            }
            result = subprocess.run(
                ["bash", "scripts/link-skills.sh"],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(marker.is_file())
            self.assertIn("Conflict", result.stderr)

    def test_versions_and_ci_guards_are_consistent(self) -> None:
        plugin = json.loads(PLUGIN_PATH.read_text(encoding="utf-8"))
        skill = (SKILLS / "email" / "SKILL.md").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")

        version = declared_version()
        self.assertEqual(plugin["version"], version)
        self.assertIn(f'version: "{version}"', skill)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("actions/checkout@", workflow)
        self.assertIn("actions/setup-python@", workflow)
        self.assertIn("actions/setup-node@", workflow)
        self.assertIn("ci-pins.py spec skills", workflow)
        self.assertIn("ci-pins.py spec claude-code", workflow)
        self.assertIn("ci-pins.py check", workflow)
        self.assertIn('python-version: ["3.11", "3.12", "3.13"]', workflow)
        self.assertIn("astral-sh/ruff-action@", workflow)
        self.assertIn("version: ${{ env.RUFF_VERSION }}", workflow)
        self.assertIn("shellcheck scripts/*.sh", workflow)

    def test_changelog_keeps_one_unreleased_section_and_descending_releases(self) -> None:
        """Two `## Unreleased` sections merge on sight, and the second one's entries vanish."""

        headings = [
            line for line in CHANGELOG_PATH.read_text(encoding="utf-8").splitlines() if line.startswith("## ")
        ]
        self.assertLessEqual(headings.count("## Unreleased"), 1, headings)
        if "## Unreleased" in headings:
            self.assertEqual(headings[0], "## Unreleased", "Unreleased belongs above every release")

        releases = []
        for heading in headings:
            if heading == "## Unreleased":
                continue
            match = RELEASE_HEADING.match(heading)
            self.assertIsNotNone(match, f"malformed release heading: {heading!r}")
            releases.append(tuple(int(part) for part in match.group(1).split(".")))

        self.assertEqual(releases, sorted(releases, reverse=True), "releases must run newest first")
        self.assertEqual(len(releases), len(set(releases)), "a version is documented twice")

    def test_changelog_documents_the_declared_version(self) -> None:
        """A bump that never closed `## Unreleased` tags a release nothing describes."""

        version = declared_version()
        changelog = CHANGELOG_PATH.read_text(encoding="utf-8")
        self.assertRegex(
            changelog,
            rf"(?m)^## {re.escape(version)} — \d{{4}}-\d{{2}}-\d{{2}}$",
            f"CHANGELOG.md has no section for the declared version {version}",
        )

    def test_release_workflow_packages_every_skill_on_tag_push(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

        self.assertIn('tags: ["v*"]', workflow)
        self.assertIn("permissions:\n  contents: write", workflow)
        self.assertIn("actions/checkout@", workflow)
        self.assertIn("actions/setup-python@", workflow)
        self.assertIn("scripts/list-skills.sh", workflow)
        self.assertIn("scripts/package-skill.py", workflow)
        self.assertIn("dist/*.skill", workflow)
        # Superseding a publish between `gh release create` and the upload
        # leaves a release with no archives on it.
        self.assertIn("cancel-in-progress: false", workflow)

        # claude.ai and Cowork take the file, not the tag, so the download is
        # the one step of the publishing path with nothing checking it.
        self.assertIn("sha256sum", workflow)
        self.assertIn("dist/SHA256SUMS", workflow)
        self.assertIn("actions/attest-build-provenance", workflow)
        for permission in ("id-token: write", "attestations: write"):
            self.assertIn(permission, workflow)

    def test_every_published_skill_has_trigger_and_non_trigger_cases(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/run-evals.py", "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_eval_check_rejects_a_missing_suite_and_a_dangling_hand_off(self) -> None:
        """A suite for a skill nobody publishes, or a hand-off to one, is drift."""

        with repository_copy() as copied:

            def run() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, "scripts/run-evals.py", "--check"],
                    cwd=copied,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            suite = copied / "evals" / "sync" / "evals.json"
            original = suite.read_text(encoding="utf-8")
            moved = suite.with_suffix(".json.moved")

            suite.rename(moved)
            self.assertIn("missing", run().stderr)
            moved.rename(suite)

            document = json.loads(original)
            document["non_triggers"][0]["routes_to"] = "no-such-skill"
            suite.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self.assertIn("not published", run().stderr)

            document["non_triggers"][0]["routes_to"] = "sync"
            suite.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self.assertIn("its own skill", run().stderr)

            document = json.loads(original)
            document["triggers"] = document["triggers"][:1]
            suite.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self.assertIn("needs at least", run().stderr)

    def test_behavior_fixtures_stay_in_their_suite_and_validate_as_v2_json(self) -> None:
        """A missing, escaping, or malformed artifact must fail before model billing."""

        with repository_copy() as copied:
            suite = copied / "evals" / "synastry-reading" / "evals.json"
            invalid = suite.parent / "invalid-behavior-fixture.json"
            stale = suite.parent / "stale-integrity-behavior-fixture.json"
            escaping_link = suite.parent / "escaping-behavior-fixture.json"
            original = suite.read_text(encoding="utf-8")

            def run_with(fixture: str) -> subprocess.CompletedProcess[str]:
                document = json.loads(original)
                document["behaviors"][0]["fixture"] = fixture
                document["behaviors"][0]["language"] = "en"
                suite.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
                return subprocess.run(
                    [sys.executable, "scripts/run-evals.py", "--check"],
                    cwd=copied,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            missing = run_with("fixtures/does-not-exist.json")
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("does not exist", missing.stderr)

            escaping = run_with("../synastry/evals.json")
            self.assertNotEqual(escaping.returncode, 0)
            self.assertIn("inside its eval suite", escaping.stderr)

            invalid.write_text("{}\n", encoding="utf-8")
            malformed = run_with(invalid.name)
            self.assertNotEqual(malformed.returncode, 0)
            self.assertIn("synastry v2 validation", malformed.stderr)

            escaping_link.symlink_to(copied / "evals" / "synastry" / "evals.json")
            symlink_escape = run_with(escaping_link.name)
            self.assertNotEqual(symlink_escape.returncode, 0)
            self.assertIn("inside its eval suite", symlink_escape.stderr)

            fixture = json.loads((suite.parent / "fixtures" / "neutral.json").read_text(encoding="utf-8"))
            fixture["chart_id"] = "aaaaaaaaaaaa"
            stale.write_text(json.dumps(fixture), encoding="utf-8")
            integrity_mismatch = run_with(stale.name)
            self.assertNotEqual(integrity_mismatch.returncode, 0)
            self.assertIn("synastry v2 validation", integrity_mismatch.stderr)

    def test_every_description_meets_the_rules_contributing_states(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/check-descriptions.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_description_rules_reject_what_they_are_written_to_reject(self) -> None:
        """Each rule is checked on its own, so a passing suite means all four hold."""

        with repository_copy() as copied:
            skills = copied / "plugins" / "writing" / "skills"
            skill_file = skills / "email" / "SKILL.md"
            original = skill_file.read_text(encoding="utf-8")
            current = next(line for line in original.splitlines() if line.startswith("description:"))
            tempering = next(
                line
                for line in (skills / "tempering" / "SKILL.md").read_text(encoding="utf-8").splitlines()
                if line.startswith("description:")
            )
            cases = {
                "placeholder": "description: PLACEHOLDER, " + "rewrite this line. " * 8 + "Not for anything.",
                "over 1024": "description: " + "words to overflow the ceiling. " * 40 + "Not for anything.",
                "under 120": "description: Short. Not for much.",
                "not for": current.split(" Not for ")[0],
                "consecutive words": tempering,
            }
            for expected, replacement in cases.items():
                skill_file.write_text(original.replace(current, replacement, 1), encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, "scripts/check-descriptions.py"],
                    cwd=copied,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0, expected)
                self.assertIn(expected, result.stderr, f"{expected} was not the rule that fired")

    def test_canary_runs_the_install_routes_against_the_latest_clis(self) -> None:
        """A pinned route never fails on upstream drift, so Install alone cannot find it."""

        canary = (ROOT / ".github" / "workflows" / "canary.yml").read_text(encoding="utf-8")
        install = (ROOT / ".github" / "workflows" / "install.yml").read_text(encoding="utf-8")

        for required in ("schedule:", "workflow_dispatch:", "channel: latest", "issues: write"):
            self.assertIn(required, canary)

        # The four routes exist once. Canary calls Install rather than copying it,
        # so a route added there is covered here without being written twice.
        self.assertIn("uses: ./.github/workflows/install.yml", canary)
        self.assertIn("workflow_call:", install)
        self.assertIn("CI_CHANNEL: ${{ inputs.channel || 'pinned' }}", install)
        for duplicated in ("verify-install.py", "list-skills.sh", "npx --yes"):
            self.assertNotIn(duplicated, canary, "canary must call Install, not restate it")

    def test_remote_evals_are_opt_in_while_local_preflight_stays_available(self) -> None:
        """Bot Fight Mode keeps the public gateway; expensive scoring happens locally for now."""

        workflow = (ROOT / ".github" / "workflows" / "evals.yml").read_text(encoding="utf-8")
        validate = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
        preflight = (ROOT / "scripts" / "run-evals-local.sh").read_text(encoding="utf-8")
        template = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")

        for required in ("workflow_dispatch:", "issues: write", "run-evals.py --run"):
            self.assertIn(required, workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertIn("if: vars.ENABLE_REMOTE_EVALS == 'true'", workflow)
        # The key is the reason this job is not in the normal gate. Interpolating
        # a dispatch input into its shell would be injection into a job holding it.
        self.assertIn("LITELLM_EVALS_API_KEY: ${{ secrets.LITELLM_EVALS_API_KEY }}", workflow)
        self.assertNotIn('"${{ inputs.skill }}"', workflow)
        self.assertIn("ci-pins.py spec openai", workflow)

        self.assertIn("LITELLM_EVALS_BASE_URL", preflight)
        self.assertIn("LITELLM_EVALS_API_KEY", preflight)
        self.assertIn("https://llm-evals.misoto22.com/v1", preflight)
        self.assertRegex(preflight, r'run-evals\.py"\s+--run(?:\s|$)')
        self.assertRegex(preflight, r'run-evals\.py"\s+--run-behaviors(?:\s|$)')
        self.assertIn("run-evals-local.sh", template)

        # Scoring costs money and minutes; the free structural half stays on
        # every push, and only that half is allowed in the normal gate.
        self.assertIn("run-evals.py --check", validate)
        self.assertNotIn("--run", validate)

    def test_behavior_fixtures_are_validated_and_executable(self) -> None:
        """Reading behavior cases have their own paid execution path."""

        runner = (ROOT / "scripts" / "run-evals.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "evals.yml").read_text(encoding="utf-8")

        self.assertIn("--run-behaviors", runner)
        # Every skill's, not one skill's. Naming a skill here left 51 of the 58
        # written behavior cases unexecuted — the expensive half of the suites,
        # and the half whose absence no other check can see.
        self.assertIn("run-evals.py --run-behaviors 2>&1", workflow)
        self.assertNotIn("--run-behaviors synastry-reading", workflow)

    def test_every_behavior_case_is_reachable_by_the_local_preflight(self) -> None:
        """A case nobody runs is documentation, and it is billed for as neither."""

        preflight = (ROOT / "scripts" / "run-evals-local.sh").read_text(encoding="utf-8")
        written = {
            path.parent.name: len(json.loads(path.read_text(encoding="utf-8")).get("behaviors") or [])
            for path in sorted((ROOT / "evals").glob("*/evals.json"))
        }
        carrying = {skill for skill, count in written.items() if count}

        self.assertGreater(len(carrying), 1, "only one skill writes behavior cases")
        for skill in sorted(carrying):
            self.assertNotIn(
                f"--run-behaviors {skill}",
                preflight,
                f"{skill} would be the only skill scored; drop the argument to score them all",
            )

    def test_mechanical_validation_is_a_registry_rather_than_a_skill_name(self) -> None:
        """A fixture-bearing case in an unregistered skill must fail, not be skipped."""

        import importlib.util

        spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run-evals.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertIn("synastry-reading", module.MECHANICAL_VALIDATORS)
        for paths in module.MECHANICAL_VALIDATORS.values():
            for role in ("reading", "source", "schema"):
                self.assertTrue(paths[role].is_file(), paths[role])

        # A skill with no entry is reported, not silently judged semantically.
        failures = module._mechanical_failures(
            "readme", {"id": "x", "fixture": "fixtures/whatever.json"}, "# draft\n"
        )
        self.assertEqual(len(failures), 1, failures)
        self.assertIn("MECHANICAL_VALIDATORS", failures[0])

        # Every skill whose cases carry a fixture has to be registered.
        for path in sorted((ROOT / "evals").glob("*/evals.json")):
            suite = json.loads(path.read_text(encoding="utf-8"))
            if any(case.get("fixture") for case in suite.get("behaviors") or []):
                self.assertIn(path.parent.name, module.MECHANICAL_VALIDATORS, path.parent.name)

    def test_every_skill_can_build_its_behavior_prompt(self) -> None:
        """The weekly run spans every skill now, and this half of it costs nothing.

        `_cli_contracts` renders `--help` for each script SKILL.md names, and
        raises when one exits nonzero. It matched an option as a subcommand, so
        three skills raised here — before a single billable call — and nothing
        noticed while behaviors ran for one skill.
        """

        import importlib.util

        spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run-evals.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        built = 0
        for path in sorted((ROOT / "evals").glob("*/evals.json")):
            skill = path.parent.name
            cases = json.loads(path.read_text(encoding="utf-8")).get("behaviors") or []
            if not cases:
                continue
            built += 1
            with self.subTest(skill=skill):
                self.assertTrue(module.behavior_system_prompt(skill).strip())
                self.assertTrue(module._behavior_user_message(skill, cases[0]).strip())
        self.assertGreater(built, 1)

    def test_a_reading_behavior_runs_mechanical_and_semantic_checks(self) -> None:
        """A valid draft still fails once for each expectation the judge rejects."""

        import importlib.util

        spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run-evals.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        run_behavior_case = getattr(module, "run_behavior_case", None)
        self.assertIsNotNone(run_behavior_case, "run_behavior_case is not implemented")
        if run_behavior_case is None:
            return

        citation = (
            "[E-ASPECT-9DAF] aspect: subject-b Moon -> subject-a Sun; "
            "direction subject-b->subject-a; kind square; certainty exact; orb 1.1°"
        )
        headings = (
            "Basis, provenance, and limitations",
            "Repeated interaction patterns",
            "Reciprocity and asymmetry",
            "Communication and coordination",
            "Tension, boundaries, and repair",
            "Growth and shared direction",
            "Requested or context-specific domains",
            "Overall synthesis",
            "Evidence index",
        )
        report = "# Synthetic synastry reading\n\n" + "\n\n".join(
            f"## {heading}\n\n{citation}" for heading in headings
        )
        judge = json.dumps(
            {
                "evaluations": [
                    {"expectation": 1, "passed": True, "reason": "All headings are present."},
                    {
                        "expectation": 2,
                        "passed": False,
                        "reason": "The requested constraint is not demonstrated.\n" + "x" * 6000,
                    },
                ]
            }
        )
        responses = [report, judge]
        requests: list[dict] = []

        class Completions:
            @staticmethod
            def create(**kwargs):
                requests.append(kwargs)
                text = responses.pop(0)
                message = type("Message", (), {"content": text})()
                choice = type("Choice", (), {"finish_reason": "stop", "message": message})()
                return type("Response", (), {"choices": [choice]})()

        class Client:
            class chat:
                completions = Completions()

        failures = run_behavior_case(
            Client(),
            "synastry-reading",
            {
                "id": "mechanical-and-semantic",
                "prompt": "Write a neutral reading from the supplied artifact.",
                "fixture": "fixtures/neutral.json",
                "language": "en",
                "expectations": ["Uses all headings.", "Demonstrates the requested constraint."],
            },
        )

        self.assertEqual(len(failures), 1, failures)
        self.assertIn("expectation 2", failures[0])
        self.assertNotIn("\n", failures[0])
        self.assertLessEqual(len(failures[0]), 512)
        self.assertEqual(len(requests), 2)
        self.assertNotIn("json_schema", json.dumps(requests[0]))
        self.assertIn("[E-ASPECT-9DAF]", requests[0]["messages"][1]["content"])
        self.assertEqual(requests[1]["response_format"], {"type": "json_object"})
        self.assertIn("output-template.md", requests[0]["messages"][0]["content"])
        self.assertIn("usage:", requests[0]["messages"][0]["content"])

    def test_a_reading_behavior_reports_every_mechanical_validator_problem(self) -> None:
        """Removing or collapsing mechanical validation must make this test fail."""

        import importlib.util

        spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run-evals.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        invalid_report = (
            "# Invalid reading\n\nCompatibility score: 99%\n\nThis relationship will definitely last.\n"
        )
        judge = json.dumps(
            {"evaluations": [{"expectation": 1, "passed": True, "reason": "Semantic expectation passes."}]}
        )
        responses = [invalid_report, judge]

        class Completions:
            @staticmethod
            def create(**kwargs):
                del kwargs
                message = type("Message", (), {"content": responses.pop(0)})()
                choice = type("Choice", (), {"finish_reason": "stop", "message": message})()
                return type("Response", (), {"choices": [choice]})()

        class Client:
            class chat:
                completions = Completions()

        failures = module.run_behavior_case(
            Client(),
            "synastry-reading",
            {
                "id": "multiple-mechanical-problems",
                "prompt": "Write a neutral reading from the supplied artifact.",
                "fixture": "fixtures/neutral.json",
                "language": "en",
                "expectations": ["Uses valid reading mechanics."],
            },
        )

        self.assertGreaterEqual(len(failures), 4, failures)
        self.assertTrue(all(failure.startswith("mechanical violation: ") for failure in failures))
        self.assertTrue(all("\n" not in failure and len(failure) <= 512 for failure in failures))
        self.assertTrue(any("compatibility score" in failure for failure in failures))
        self.assertTrue(any("required universal heading" in failure for failure in failures))

    def test_model_text_response_reads_the_first_chat_completion(self) -> None:
        """The OpenAI-compatible API keeps the generated text on its first choice."""

        import importlib.util

        spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run-evals.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        message = type("Message", (), {"content": "first second"})()
        choice = type("Choice", (), {"finish_reason": "stop", "message": message})()
        response = type("Response", (), {"choices": [choice]})()

        self.assertEqual(module._response_text(response), "first second")

    def test_the_scoring_mode_stays_out_of_the_standard_library_path(self) -> None:
        """--check and --report run everywhere; only --run may need a dependency."""

        source = (ROOT / "scripts" / "run-evals.py").read_text(encoding="utf-8")
        top_level = source.split("def ", 1)[0]

        self.assertNotIn("import openai", top_level, "the SDK import must be lazy")
        self.assertIn("import openai", source)
        # Named once, where the pin lives — a literal here could not be bumped
        # by ci-pins.py and would drift silently.
        self.assertIn("ci-pins.py spec openai", source)

        pins = json.loads((ROOT / ".ci-pins.json").read_text(encoding="utf-8"))["pins"]
        self.assertIn("openai", {pin["id"] for pin in pins})

    def test_evals_use_a_scoped_litellm_endpoint_not_a_provider_endpoint(self) -> None:
        """The CI key must be a model-scoped gateway key, never a provider credential."""

        source = (ROOT / "scripts" / "run-evals.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "evals.yml").read_text(encoding="utf-8")

        self.assertIn("def _litellm_client()", source)
        self.assertIn('os.environ.get("LITELLM_EVALS_BASE_URL")', source)
        self.assertIn('os.environ.get("LITELLM_EVALS_API_KEY")', source)
        self.assertNotIn("https://api.deepseek.com", source)
        self.assertIn("LITELLM_EVALS_BASE_URL: https://llm-evals.misoto22.com/v1", workflow)
        self.assertIn("LITELLM_EVALS_API_KEY: ${{ secrets.LITELLM_EVALS_API_KEY }}", workflow)
        self.assertNotIn("DEEPSEEK_API_KEY:", workflow)

    def test_the_router_request_is_shaped_the_way_the_api_expects(self) -> None:
        """This request runs in the local preflight. Pin its shape here.

        Every assertion below is a parameter the current API rejects outright or
        silently ignores if it is wrong — a 400 nobody sees for a week, or a run
        that scores the wrong thing and reports success.
        """

        import importlib.util

        spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run-evals.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        sent = {}

        message = type("Message", (), {"content": '{"skill": "ship", "reason": "x"}'})()
        choice = type("Choice", (), {"message": message, "finish_reason": "stop"})()
        response = type("Response", (), {"choices": [choice]})()

        class Client:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        sent.update(kwargs)
                        return response

        answer, reason = module.route(Client(), "<skills/>", "ship it")
        self.assertEqual((answer, reason), ("ship", "x"))

        # The OpenAI-compatible endpoint needs one JSON-object request shape;
        # Anthropic-only cache controls, effort, and schema wrappers do not apply.
        for rejected in ("temperature", "top_p", "top_k", "thinking", "output_config"):
            self.assertNotIn(rejected, sent, f"{rejected} must not be sent")
        self.assertEqual(sent["response_format"], {"type": "json_object"})
        self.assertGreaterEqual(sent["max_tokens"], 1024)
        self.assertIn(
            "never invent or paraphrase a skill name",
            sent["messages"][0]["content"],
        )
        self.assertEqual(
            sent["messages"],
            [
                {"role": "system", "content": module.ROUTER_SYSTEM.format(catalogue="<skills/>")},
                {"role": "user", "content": "ship it"},
            ],
        )

    def test_router_catalogue_uses_short_labels_not_skill_slugs(self) -> None:
        """The gateway's secret guard must not redact the selected skill name."""

        import importlib.util

        spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run-evals.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        catalogue, labels = module.router_catalogue(
            {
                "cleanup": "Remove what a release left behind.",
                "photo-abstract-editorial-native": "Compose a supplied comparison board.",
            }
        )

        self.assertEqual(
            labels,
            {"s01": "cleanup", "s02": "photo-abstract-editorial-native"},
        )
        self.assertIn("<skill name='s01'>Remove what a release left behind.</skill>", catalogue)
        self.assertIn("<skill name='s02'>Compose a supplied comparison board.</skill>", catalogue)
        self.assertNotIn("photo-abstract-editorial-native", catalogue)

    def test_a_non_trigger_is_satisfied_by_no_skill_firing(self) -> None:
        """`none` is the right answer for most non-triggers, and must score as a pass."""

        import importlib.util

        spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run-evals.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        known = {"ship", "cleanup", "sync"}
        cases = [
            # (section, case, answer, expected pass?)
            ("triggers", {"id": "a"}, "ship", True),
            ("triggers", {"id": "a"}, "none", False),
            ("non_triggers", {"id": "b"}, "none", True),
            ("non_triggers", {"id": "b"}, "ship", False),
            ("non_triggers", {"id": "c", "routes_to": "cleanup"}, "cleanup", True),
            ("non_triggers", {"id": "c", "routes_to": "cleanup"}, "sync", False),
            ("non_triggers", {"id": "d"}, "invented", False),
        ]
        for section, case, answer, passes in cases:
            verdict = module._judge("ship", section, case, answer, known)
            self.assertEqual(verdict is None, passes, f"{section} {case['id']} → {answer}: {verdict}")

    def test_a_declined_request_is_read_before_its_content(self) -> None:
        """A refusal returns 200 with empty content; indexing it first crashes the run."""

        import importlib.util

        spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run-evals.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class Refused:
            choices: ClassVar[list[object]] = [
                type("Choice", (), {"finish_reason": "content_filter", "message": None})()
            ]

        class Client:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        return Refused()

        answer, reason = module.route(Client(), "<skills/>", "anything")
        self.assertEqual(answer, "refused")
        self.assertIn("declined", reason)

    def test_an_empty_router_response_fails_a_case_without_crashing_evals(self) -> None:
        """A gateway 200 without text is invalid model output, not valid JSON."""

        import importlib.util

        spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run-evals.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class Empty:
            choices: ClassVar[list[object]] = [
                type(
                    "Choice",
                    (),
                    {"finish_reason": "stop", "message": type("Message", (), {"content": ""})()},
                )()
            ]

        class Client:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        return Empty()

        answer, reason = module.route(Client(), "<skills/>", "anything")
        self.assertEqual(answer, "invalid")
        self.assertIn("empty", reason)

    def test_the_router_retries_one_transient_empty_response(self) -> None:
        """A one-off empty LiteLLM response must not invalidate an otherwise sound suite."""

        import importlib.util

        spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run-evals.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class Empty:
            choices: ClassVar[list[object]] = [
                type(
                    "Choice",
                    (),
                    {"finish_reason": "stop", "message": type("Message", (), {"content": ""})()},
                )()
            ]

        class Valid:
            choices: ClassVar[list[object]] = [
                type(
                    "Choice",
                    (),
                    {
                        "finish_reason": "stop",
                        "message": type(
                            "Message",
                            (),
                            {"content": '{"skill": "ship", "reason": "matches"}'},
                        )(),
                    },
                )()
            ]

        class Client:
            calls: ClassVar[int] = 0
            responses: ClassVar[list[object]] = [Empty(), Valid()]

            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        response = Client.responses[Client.calls]
                        Client.calls += 1
                        return response

        answer, reason = module.route(Client(), "<skills/>", "anything")
        self.assertEqual((answer, reason), ("ship", "matches"))
        self.assertEqual(Client.calls, 2)

    def test_semantic_judge_rejects_an_incomplete_evaluation_object(self) -> None:
        """A missing verdict must be reported as invalid output instead of aborting a behavior run."""

        import importlib.util

        spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run-evals.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class Response:
            choices: ClassVar[list[object]] = [
                type(
                    "Choice",
                    (),
                    {
                        "finish_reason": "stop",
                        "message": type(
                            "Message",
                            (),
                            {
                                "content": json.dumps(
                                    {"evaluations": [{"expectation": 1, "reason": "missing verdict"}]}
                                )
                            },
                        )(),
                    },
                )()
            ]

        class Client:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        return Response()

        result = module._semantic_failures(
            Client(),
            {"prompt": "anything", "expectations": ["The draft preserves the source."]},
            "candidate markdown",
        )
        self.assertEqual(result, ["semantic judge returned an invalid result"])

    def test_ci_pins_are_the_only_place_a_cli_version_is_written(self) -> None:
        """A literal pin cannot be overridden by a channel, so the canary would miss it."""

        result = subprocess.run(
            [sys.executable, "scripts/ci-pins.py", "check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ci_pin_spec_resolves_the_declared_version_and_the_latest_channel(self) -> None:
        pins = json.loads((ROOT / ".ci-pins.json").read_text(encoding="utf-8"))["pins"]
        self.assertTrue(pins)
        for pin in pins:
            # npm and pip spell a pin differently, so a pin may carry its own
            # template. The default is the npm form every other one uses.
            pinned = pin.get("spec", "{package}@{version}")
            latest = pin.get("spec_latest", "{package}@latest")
            # Both templates see both fields. A pin that cannot float — a
            # runtime, the evaluation model — says so by resolving `latest` to
            # the version it already declares, which needs {version} here.
            for channel, expected in (
                ("pinned", pinned.format(package=pin["package"], version=pin["version"])),
                ("latest", latest.format(package=pin["package"], version=pin["version"])),
            ):
                result = subprocess.run(
                    [sys.executable, "scripts/ci-pins.py", "spec", pin["id"]],
                    cwd=ROOT,
                    env={**os.environ, "CI_CHANNEL": channel},
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertEqual(result.stdout.strip(), expected, pin["id"])

        unknown = subprocess.run(
            [sys.executable, "scripts/ci-pins.py", "spec", "no-such-cli"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(unknown.returncode, 0)

    def test_ci_pin_bump_moves_every_documented_occurrence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = copy_repository_fixture(Path(temporary))
            config_path = copied / ".ci-pins.json"
            pins = json.loads(config_path.read_text(encoding="utf-8"))["pins"]
            documented = [pin for pin in pins if pin.get("documented_in")]
            self.assertTrue(documented, "no pin is written down outside .ci-pins.json")

            before = {
                path: (copied / path).read_bytes() for pin in documented for path in pin["documented_in"]
            }
            for pin in documented:
                target = bumped_version(pin)
                self.assertNotEqual(target, pin["version"], pin["id"])
                moved = subprocess.run(
                    [sys.executable, "scripts/ci-pins.py", "bump", pin["id"], target],
                    cwd=copied,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(moved.returncode, 0, moved.stderr)
                for path in pin["documented_in"]:
                    self.assertNotEqual((copied / path).read_bytes(), before[path], path)

            # Every occurrence moved together, so the tree agrees with itself again.
            checked = subprocess.run(
                [sys.executable, "scripts/ci-pins.py", "check"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_ci_pin_bump_refuses_a_version_of_the_wrong_shape(self) -> None:
        """A runtime is `3.13` and a model is a name; only semver pins take semver."""

        pins = json.loads((ROOT / ".ci-pins.json").read_text(encoding="utf-8"))["pins"]
        shaped = [pin for pin in pins if pin.get("version_pattern")]
        self.assertTrue(shaped, "no pin declares its own version shape")

        with tempfile.TemporaryDirectory() as temporary:
            copied = copy_repository_fixture(Path(temporary))
            for pin in shaped:
                # A three-part semver is the wrong shape for every pin that had
                # to declare one; that is why they declare one.
                refused = subprocess.run(
                    [sys.executable, "scripts/ci-pins.py", "bump", pin["id"], "9.9.9"],
                    cwd=copied,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(refused.returncode, 0, pin["id"])
                self.assertIn("does not match", refused.stderr, pin["id"])

    def test_coverage_floors_the_python_that_ships(self) -> None:
        """A floor nobody runs is a floor that does not exist, so CI has to run it."""

        config = (ROOT / ".coveragerc").read_text(encoding="utf-8")
        self.assertIn("source = plugins", config)
        self.assertRegex(config, r"(?m)^fail_under = \d+$")

        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
        self.assertIn("ci-pins.py spec coverage", workflow)
        self.assertIn("coverage run -m unittest", workflow)

        # Scoped to plugins/ on purpose: the repository's own scripts are driven
        # through subprocess here, so their coverage would measure this file.
        self.assertNotIn("source = scripts", config)

    def test_every_action_is_pinned_to_a_commit(self) -> None:
        """A tag is a moving reference. Whoever can move it can change what CI runs."""

        pinned = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40} # \S+$")
        seen = 0
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped.startswith(("- uses:", "uses:")):
                    continue
                reference = stripped.split("uses:", 1)[1].strip()
                # A reusable workflow in this repository moves with this repository.
                if reference.startswith("./"):
                    continue
                seen += 1
                self.assertRegex(
                    reference,
                    pinned,
                    f"{path.name}: {reference} is not pinned to a commit with its version in a comment",
                )
        self.assertTrue(seen, "no external action found to check")

    def test_every_workflow_job_is_bounded_and_supersedes_its_own_runs(self) -> None:
        """An unbounded job holds a runner for six hours, and a superseded one burns it twice."""

        workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertTrue(workflows)
        for path in workflows:
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertRegex(
                "\n".join(lines),
                r"(?m)^concurrency:\n  group: \$\{\{ github\.workflow \}\}",
                path.name,
            )
            self.assertRegex("\n".join(lines), r"(?m)^  cancel-in-progress: (true|false)$", path.name)

            runners = [index for index, line in enumerate(lines) if line.strip().startswith("runs-on:")]
            self.assertTrue(runners, f"{path.name} defines no job")
            for index in runners:
                self.assertRegex(
                    lines[index + 1],
                    r"^\s+timeout-minutes: \d+$",
                    f"{path.name}: the job at line {index + 1} runs without a timeout",
                )

    def test_release_workflow_refuses_a_tag_the_manifests_do_not_declare(self) -> None:
        """The guard parses `--check`, so that command's output shape is part of the contract."""

        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/bump-version.py --check", workflow)
        self.assertIn("$GITHUB_REF_NAME", workflow)

        parsed = subprocess.run(
            ["bash", "-c", "python3 scripts/bump-version.py --check | awk '{print $NF}'"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(parsed.stdout.strip(), declared_version())

    def test_release_can_be_dispatched_and_still_resolves_one_tag(self) -> None:
        """Dispatch exists for callers that can start a workflow but not push a tag."""

        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("inputs:", workflow)
        self.assertIn("REQUESTED: ${{ inputs.version }}", workflow)
        # Interpolating an input straight into a script would be injection into a
        # job holding contents: write and a signing identity.
        self.assertNotIn("${{ inputs.version }}\n          run:", workflow)
        self.assertNotIn('"${{ inputs.version }}"', workflow)

        # A dispatch runs from whatever ref it was started on.
        self.assertIn("github.event.repository.default_branch", workflow)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", workflow)

        # Both triggers resolve to one $TAG. $GITHUB_REF_NAME is a branch name on
        # a dispatch, so anything downstream still reading it would publish under
        # the wrong name.
        after = workflow.split('echo "TAG=v$declared"', 1)[1]
        self.assertNotIn("GITHUB_REF_NAME", after)
        for command in ("gh release view", "gh release upload", "gh release create"):
            self.assertIn(f'{command} "$TAG"', after)

    def test_install_workflow_covers_every_supported_route(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "install.yml").read_text(encoding="utf-8")

        for route in (
            'claude plugin install "$plugin@$MARKETPLACE"',
            'codex plugin add "$plugin@$MARKETPLACE"',
            "bash scripts/list-plugins.sh",
            "bash scripts/list-skills.sh",
            "bash scripts/marketplace-name.sh",
            "scripts/package-skill.py",
            "ci-pins.py spec claude-code",
            "ci-pins.py spec codex",
            "ci-pins.py spec skills",
        ):
            self.assertIn(route, workflow)
        self.assertEqual(workflow.count("scripts/verify-install.py"), 4)

    def test_install_workflow_names_no_plugin_skill_or_marketplace(self) -> None:
        """A name written here is a name that has to be maintained here. Derive them."""

        workflow = (ROOT / ".github" / "workflows" / "install.yml").read_text(encoding="utf-8")
        published = {path.parent.name for path in PLUGINS.glob("*/skills/*/SKILL.md")}
        published |= {path.parent.parent.name for path in PLUGINS.glob("*/.claude-plugin/plugin.json")}
        # The marketplace name too: it is the install suffix, so writing it here
        # is the same rename spread over a seventh file.
        published |= {marketplace_name()}

        for name in sorted(published):
            self.assertNotRegex(
                workflow,
                rf"\b{re.escape(name)}\b",
                f"install.yml names {name!r}; derive it from the tree instead",
            )
        self.assertEqual(workflow.count("--expect"), 4, "every route asserts a derived --expect list")

    def test_no_workflow_names_a_skill_requirements_file(self) -> None:
        """A skill declares its own dependencies; CI must not name the path."""

        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            self.assertNotIn(
                "requirements.txt",
                path.read_text(encoding="utf-8"),
                f"{path.name} names a requirements path; use scripts/install-skill-requirements.sh",
            )

    def test_python_packages_are_installed_through_uv_not_pip(self) -> None:
        """pip is one edit away from creeping back, and nothing else would notice."""

        installers = {
            "scripts/install-skill-requirements.sh",
            "scripts/run-evals-local.sh",
            ".github/workflows/validate.yml",
            ".github/workflows/evals.yml",
        }
        for relative in sorted(installers):
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(file=relative):
                self.assertNotRegex(
                    text,
                    r"(?<!uv )pip install|python3? -m pip|python3? -m venv",
                    f"{relative} installs with pip; this repository installs with uv",
                )
                self.assertIn("uv ", text, f"{relative} names no uv command")

        # setup-uv takes its version as an input, so a workflow holds the literal
        # and ci-pins.py is what keeps that literal honest.
        for relative in (".github/workflows/validate.yml", ".github/workflows/evals.yml"):
            workflow = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(file=relative):
                self.assertIn("astral-sh/setup-uv@", workflow)
                self.assertIn("version: ${{ env.UV_VERSION }}", workflow)
                # A runner has no virtual environment. Declaring that here rather
                # than naming an interpreter in the script is what keeps the same
                # script safe on a contributor's machine.
                self.assertIn("UV_SYSTEM_PYTHON: 1", workflow)

        # The shared installer must stay interpreter-agnostic, or the CI decision
        # travels to a laptop and silently writes into someone's global Python.
        installer = (ROOT / "scripts" / "install-skill-requirements.sh").read_text(encoding="utf-8")
        self.assertNotIn("--system", installer)
        self.assertNotIn("command -v python3", installer)
        self.assertIn("uv pip install --requirement", installer)

        pins = json.loads((ROOT / ".ci-pins.json").read_text(encoding="utf-8"))["pins"]
        uv_pin = next((pin for pin in pins if pin["id"] == "uv"), None)
        self.assertIsNotNone(uv_pin, "uv has no pin, so its version can drift unnoticed")
        self.assertEqual(uv_pin["match"], 'UV_VERSION: "{version}"')
        self.assertEqual(
            sorted(uv_pin["documented_in"]),
            [".github/workflows/evals.yml", ".github/workflows/validate.yml"],
        )

    def test_no_root_python_project_competes_with_the_pin_file(self) -> None:
        """A lockfile at the root would be a second source of truth for versions.

        It would also never reach an installed skill, which is copied out on its
        own. Dependencies belong to the skill that needs them.
        """

        for stray in ("pyproject.toml", "uv.lock", "requirements.txt", "setup.py"):
            self.assertFalse((ROOT / stray).exists(), f"{stray} duplicates .ci-pins.json")

    def test_every_skill_whose_script_needs_an_ephemeris_declares_it(self) -> None:
        """A missing declaration passes CI only while another skill installs it."""

        for scripts in sorted(PLUGINS.glob("*/skills/*/scripts")):
            skill = scripts.parent
            needs = any("swisseph" in path.read_text(encoding="utf-8") for path in scripts.rglob("*.py"))
            if not needs:
                continue
            requirements = skill / "requirements.txt"
            with self.subTest(skill=skill.name):
                self.assertTrue(
                    requirements.is_file(),
                    f"{skill.name} imports swisseph but declares no requirements.txt",
                )
                self.assertIn("pyswisseph", requirements.read_text(encoding="utf-8"))

    def test_install_skill_requirements_finds_every_declared_dependency(self) -> None:
        """The script is what CI runs, so what it finds has to be the whole set."""

        result = subprocess.run(
            ["bash", "scripts/install-skill-requirements.sh", "--list"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        declared = sorted(
            path.relative_to(ROOT).as_posix() for path in PLUGINS.glob("*/skills/*/requirements.txt")
        )

        self.assertTrue(declared, "no skill declares a dependency; this test has nothing to hold")
        self.assertEqual(sorted(result.stdout.split()), declared)

    def test_list_script_prints_only_published_plugins(self) -> None:
        result = subprocess.run(
            ["bash", "scripts/list-plugins.sh"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        expected = sorted(
            f"{path.parent.parent.name}\n" for path in PLUGINS.glob("*/.claude-plugin/plugin.json")
        )
        self.assertEqual(result.stdout, "".join(expected))

    def test_verify_install_rejects_a_tree_missing_shared(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            broken = Path(temporary) / "email"
            shutil.copytree(SKILLS / "email", broken)
            shutil.rmtree(broken / "shared")

            result = subprocess.run(
                [sys.executable, "scripts/verify-install.py", str(broken)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("the install dropped shared material", result.stderr)

    def test_verify_install_accepts_the_published_tree(self) -> None:
        # Every published skill, derived. Naming three of them asserted less on
        # each skill added, and silently: the check kept passing while covering
        # a smaller share of the tree.
        expected: list[str] = []
        for skills in published_skills().values():
            for skill in skills:
                expected.extend(("--expect", skill))
        self.assertTrue(expected)

        subprocess.run(
            [sys.executable, "scripts/verify-install.py", str(PLUGINS), *expected],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )

    def test_version_bump_declares_every_occurrence(self) -> None:
        """--audit is the half that matters: it catches a file nobody declared."""

        result = subprocess.run(
            [sys.executable, "scripts/bump-version.py", "--audit"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no undeclared occurrences", result.stdout)

    def test_version_audit_reaches_the_workflows_directory(self) -> None:
        """Excluding `.git` by string prefix excluded `.github` with it, silently."""

        with repository_copy() as copied:
            probe = copied / ".github" / "workflows" / "audit-probe.yml"
            probe.write_text(f"probe: {declared_version()}\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "scripts/bump-version.py", "--audit"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(".github/workflows/audit-probe.yml", result.stderr)

    def test_neither_scanner_walks_into_a_checkout_outside_dot_claude(self) -> None:
        """A worktree lives wherever someone put it, not only under .claude/.

        The configured exclusion covered one location. A `git worktree add` to any
        other path — or a submodule, or a stray clone — put a second copy of every
        manifest back in the scan, and both scanners reported files nobody in this
        checkout wrote. What marks a nested checkout is its own `.git`, so that is
        what the scanners now skip.
        """

        with repository_copy() as copied:
            for location in (".worktrees/elsewhere", "vendor/nested", "deep/a/b/checkout"):
                nested = copied / location
                nested.mkdir(parents=True, exist_ok=True)
                (nested / ".git").write_text("gitdir: /somewhere/else\n", encoding="utf-8")
                pin = json.loads((copied / ".ci-pins.json").read_text(encoding="utf-8"))["pins"][0]
                (nested / "README.md").write_text(
                    f"version {declared_version()}\n{pin['package']}@{pin['version']}\n",
                    encoding="utf-8",
                )

            for command in (
                ("scripts/bump-version.py", "--audit"),
                ("scripts/ci-pins.py", "check"),
            ):
                result = subprocess.run(
                    [sys.executable, *command],
                    cwd=copied,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                with self.subTest(command=command[0]):
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    for location in (".worktrees/elsewhere", "vendor/nested", "deep/a/b/checkout"):
                        self.assertNotIn(location, result.stdout + result.stderr)

    def test_neither_scanner_walks_into_a_worktree(self) -> None:
        """A worktree under .claude/ is a second copy of this repository, not drift.

        Both scanners recurse from the repository root, and a `git worktree` placed
        inside it holds every manifest, README and CHANGELOG again. CI never sees
        this — a checkout has no worktrees — so the failure lands only on whoever
        has one open, reporting files they did not write as undeclared.
        """

        with repository_copy() as copied:
            probe = copied / ".claude" / "worktrees" / "scanner-probe" / "CHANGELOG.md"
            probe.parent.mkdir(parents=True, exist_ok=True)
            pin = json.loads((copied / ".ci-pins.json").read_text(encoding="utf-8"))["pins"][0]
            probe.write_text(
                f"version {declared_version()}\n{pin['package']}@{pin['version']}\n",
                encoding="utf-8",
            )
            for command in (
                ("scripts/bump-version.py", "--audit"),
                ("scripts/ci-pins.py", "check"),
            ):
                result = subprocess.run(
                    [sys.executable, *command],
                    cwd=copied,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, f"{command}: {result.stderr}")
                self.assertNotIn("scanner-probe", result.stderr, str(command))

    def test_version_bump_round_trips_without_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = copy_repository_fixture(Path(temporary))
            config = json.loads((copied / ".version-bump.json").read_text(encoding="utf-8"))
            declared = [entry["path"] for entry in config["json"]] + config["text"]
            before = {path: (copied / path).read_bytes() for path in declared}
            original = declared_version()

            def run(*args: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, "scripts/bump-version.py", *args],
                    cwd=copied,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            self.assertEqual(run("9.9.9").returncode, 0)
            self.assertIn("current version: 9.9.9", run("--check").stdout)
            for path in declared:
                self.assertNotEqual((copied / path).read_bytes(), before[path], path)

            # Back to where it started, byte for byte. Read from the validator
            # rather than written here: a literal in this file would be one more
            # occurrence for the bumper to declare and move.
            self.assertEqual(run(original).returncode, 0)
            for path in declared:
                self.assertEqual((copied / path).read_bytes(), before[path], path)

            self.assertNotEqual(run("bad-version").returncode, 0)

    def test_new_skill_scaffold_leaves_only_the_description_to_write(self) -> None:
        """The scaffold owes the registries nothing, and owes the description everything."""

        with repository_copy() as copied:
            scaffolded = copied / "plugins" / "scaffoldtest"
            created = subprocess.run(
                [sys.executable, "scripts/new-skill.py", "scaffoldtest", "probe"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stderr)

            validated = subprocess.run(
                [sys.executable, "scripts/validate-repository.py", "--skip-tests"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )
            # Every registry check passes; the placeholder description is the
            # only thing left, which is exactly what new-skill.py tells you.
            self.assertNotEqual(validated.returncode, 0, validated.stdout)
            reported = [line for line in validated.stderr.splitlines() if line.startswith("error:")]
            self.assertTrue(reported, validated.stderr)
            for line in reported:
                self.assertIn("scaffoldtest/skills/probe/SKILL.md", line)
                self.assertIn("placeholder", line.lower())
            self.assertTrue((scaffolded / "skills" / "probe" / "agents" / "openai.yaml").is_file())
            self.assertIn(
                "license: MIT",
                (scaffolded / "skills" / "probe" / "SKILL.md").read_text(encoding="utf-8"),
            )
            for manifest in (
                scaffolded / "plugin.json",
                scaffolded / ".claude-plugin" / "plugin.json",
            ):
                self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["license"], "MIT")

    def test_new_skill_inherits_an_existing_plugin_license(self) -> None:
        """A new astrology skill must not be scaffolded under a conflicting MIT license."""

        with tempfile.TemporaryDirectory() as temporary:
            copied = copy_repository_fixture(Path(temporary))
            created = subprocess.run(
                [sys.executable, "scripts/new-skill.py", "astrology", "license-probe"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(created.returncode, 0, created.stderr)
            skill = copied / "plugins" / "astrology" / "skills" / "license-probe" / "SKILL.md"
            self.assertIn("license: AGPL-3.0-or-later", skill.read_text(encoding="utf-8"))

            subprocess.run(
                [sys.executable, "scripts/sync-shared.py"],
                cwd=copied,
                check=True,
                capture_output=True,
                text=True,
            )
            validated = subprocess.run(
                [sys.executable, "scripts/validate-repository.py", "--skip-tests"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotIn("license must be", validated.stderr)

    def test_remove_skill_is_the_exact_inverse_of_new_skill(self) -> None:
        """Scaffold then retire has to leave every registry byte-identical."""

        with repository_copy() as copied:
            registries = REGISTRIES
            before = {path: (copied / path).read_bytes() for path in registries}

            self._run_in(copied, "scripts/new-skill.py", "roundtrip", "probe")
            self.assertNotEqual(
                (copied / "README.md").read_bytes(), before["README.md"], "scaffold changed nothing"
            )

            self._run_in(copied, "scripts/remove-skill.py", "roundtrip", "probe", "--delete")
            for path in registries:
                self.assertEqual((copied / path).read_bytes(), before[path], path)
            self.assertFalse(
                (copied / "plugins" / "roundtrip").exists(), "the emptied plugin was left behind"
            )

    def test_a_retired_skill_leaves_every_published_surface(self) -> None:
        """deprecated/ is only useful if nothing published can still see into it."""

        with repository_copy() as copied:
            retired = copied / "deprecated" / "roundtrip"

            self._run_in(copied, "scripts/new-skill.py", "roundtrip", "probe")
            unwritten = self._run_in(
                copied, "scripts/validate-repository.py", "--skip-tests", expect_success=False
            )
            self.assertNotEqual(unwritten.returncode, 0, "a placeholder description validated")

            self._run_in(copied, "scripts/remove-skill.py", "roundtrip", "probe")
            self.assertTrue((retired / "probe" / "SKILL.md").is_file(), "the material was not kept")

            # The retired tree still carries a version and a description that no
            # longer meet the published rules. Nothing may look at it.
            for command in (
                ("scripts/validate-repository.py", "--skip-tests"),
                ("scripts/bump-version.py", "--audit"),
                ("scripts/check-descriptions.py",),
                ("scripts/run-evals.py", "--check"),
                ("scripts/ci-pins.py", "check"),
            ):
                self._run_in(copied, *command)

            listed = subprocess.run(
                ["bash", "scripts/list-skills.sh"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertNotIn("probe", listed.stdout)

    def test_retiring_a_skill_clears_the_hand_offs_that_named_it(self) -> None:
        """A routes_to naming a retired skill fails --check, so removal has to own it."""

        # A real skill, moved to deprecated/ and its hand-offs cleared. In the
        # checkout this used to put `writing/tempering` back with shutil.move in
        # a finally block; an interrupted run left the skill sitting under
        # deprecated/ and the registries half-rewritten.
        routed_evals = sorted(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "evals").glob("*/evals.json")
            if '"routes_to": "tempering"' in path.read_text(encoding="utf-8")
        )
        self.assertTrue(routed_evals, "no suite hands off to tempering; this test holds nothing")

        with repository_copy() as copied:
            before = {path: (copied / path).read_bytes() for path in routed_evals}
            routed_case_ids = {
                path: {case["id"] for case in json.loads(before[path])["non_triggers"]}
                for path in routed_evals
            }

            # Without --delete, so the move is reversible and nothing is destroyed.
            self._run_in(copied, "scripts/remove-skill.py", "writing", "tempering")
            self.assertTrue((copied / "deprecated" / "writing" / "tempering" / "SKILL.md").is_file())
            for path in routed_evals:
                self.assertNotIn(b'"routes_to": "tempering"', (copied / path).read_bytes(), path)
                suite = json.loads((copied / path).read_text(encoding="utf-8"))
                self.assertEqual(
                    {case["id"] for case in suite["non_triggers"]},
                    routed_case_ids[path],
                    path,
                )
            self._run_in(copied, "scripts/run-evals.py", "--check")

    def _run(self, *command: str, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
        return self._run_in(ROOT, *command, expect_success=expect_success)

    def _run_in(
        self,
        cwd: Path,
        *command: str,
        expect_success: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run one of the repository's scripts against a chosen checkout.

        Most callers want a copy rather than this one: a script that rewrites
        registries, interrupted, leaves the real tree half-edited.
        """

        result = subprocess.run(
            [sys.executable, *command],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if expect_success:
            self.assertEqual(result.returncode, 0, f"{command}: {result.stderr}")
        return result

    def test_new_skill_rejects_names_the_marketplace_sync_would_reject(self) -> None:
        # In a copy: a name that slipped past the check would otherwise scaffold
        # a skill into the checkout, and this test has no cleanup for that.
        with repository_copy() as copied:
            for name in ("Writing", "my_skill", "1skill"):
                result = subprocess.run(
                    [sys.executable, "scripts/new-skill.py", "writing", name],
                    cwd=copied,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn("kebab-case", result.stderr)

    def test_contributor_guardrails_exist(self) -> None:
        for relative in (
            "CONTRIBUTING.md",
            ".github/PULL_REQUEST_TEMPLATE.md",
            ".github/dependabot.yml",
            ".github/ISSUE_TEMPLATE/skill-misfires.md",
            ".github/ISSUE_TEMPLATE/install-broken.md",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

        for relative in ("SECURITY.md", ".github/CODEOWNERS"):
            self.assertTrue((ROOT / relative).is_file(), relative)

        # The email skill is the one carrying send authority, so a reviewer has
        # to be named for it explicitly rather than by the catch-all.
        codeowners = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
        for path in ("*", "/plugins/writing/skills/email/", "/.github/workflows/", "/.ci-pins.json"):
            self.assertIn(path, codeowners)

        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("security/advisories/new", security)
        self.assertIn("references/security-model.md", security)
        self.assertIn("gh attestation verify", security)

        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        for command in (
            "scripts/new-skill.py",
            "scripts/bump-version.py",
            "scripts/validate-repository.py",
            "shellcheck scripts/*.sh",
            "scripts/run-evals-local.sh",
        ):
            self.assertIn(command, contributing)

        dependabot = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        self.assertIn("package-ecosystem: github-actions", dependabot)

    def test_readme_renders_no_broken_images(self) -> None:
        """A placeholder inside src= is not a note to the author; it is a broken icon."""

        import re

        readme = README_PATH.read_text(encoding="utf-8")
        for attribute in re.findall(r'(?:src|srcset)="([^"]+)"', readme):
            self.assertNotIn("[", attribute, f"placeholder left in an attribute: {attribute}")
            if attribute.startswith("http"):
                continue
            self.assertTrue((ROOT / attribute).is_file(), f"{attribute} is not committed")

    def test_centred_lines_do_not_wrap(self) -> None:
        """A centred sentence past ~70 characters wraps and strands its last line."""

        import re

        readme = README_PATH.read_text(encoding="utf-8")
        centred = re.search(r'<div align="center">(.*?)</div>', readme, re.DOTALL)
        self.assertIsNotNone(centred)
        for line in centred.group(1).splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("<", "[![", "|")):
                continue
            # What wraps is the rendered text, not the source: a line of links is
            # long in markdown and short on the page.
            rendered = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", stripped)
            self.assertLessEqual(len(rendered), 70, f"centred line wraps: {rendered}")

    def test_no_table_ships_an_empty_header_row(self) -> None:
        """Markdown cannot omit a table header; an empty one renders as a blank row."""

        readme = README_PATH.read_text(encoding="utf-8")
        lines = readme.splitlines()
        for index, line in enumerate(lines[:-1]):
            stripped = line.strip()
            if not stripped.startswith("|") or not lines[index + 1].strip().startswith("|:"):
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            self.assertTrue(
                any(cells),
                f"line {index + 1}: empty header row — write this table as HTML <tr><td>",
            )

    def test_hero_serves_both_themes(self) -> None:
        readme = README_PATH.read_text(encoding="utf-8")

        self.assertIn("(prefers-color-scheme: dark)", readme)
        for variant in ("assets/hero-dark.svg", "assets/hero-light.svg"):
            self.assertTrue((ROOT / variant).is_file(), variant)
            ET.parse(ROOT / variant)

    def test_skills_sh_groupings_match_the_published_skills(self) -> None:
        """skills.sh renders this file, so nothing here fails until a user sees it."""

        config = json.loads((ROOT / "skills.sh.json").read_text(encoding="utf-8"))
        grouped = [skill for group in config["groupings"] for skill in group["skills"]]
        published = {path.parent.name for path in PLUGINS.glob("*/skills/*/SKILL.md")}

        self.assertEqual(sorted(grouped), sorted(published))
        self.assertEqual(len(grouped), len(set(grouped)), "a skill appears in two groups")

        titles = [group["title"] for group in config["groupings"]]
        # The skills CLI title-cases a plugin name for its own group headings. This
        # page renders the string as written, so it carries the same casing rather
        # than the raw kebab-case name.
        plugins = {
            path.parent.parent.name.replace("-", " ").title()
            for path in PLUGINS.glob("*/.claude-plugin/plugin.json")
        }
        self.assertEqual(set(titles), plugins, "groups should mirror the plugins")

        for group in config["groupings"]:
            self.assertTrue(group.get("description", "").strip(), group["title"])

    def test_repository_validator_accepts_the_checkout(self) -> None:
        subprocess.run(
            [sys.executable, "scripts/validate-repository.py", "--skip-tests"],
            cwd=ROOT,
            check=True,
        )

    def test_package_is_deterministic_and_excludes_cache_files(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            for destination in (Path(first), Path(second)):
                subprocess.run(
                    [
                        sys.executable,
                        "scripts/package-skill.py",
                        "plugins/writing/skills/email",
                        str(destination),
                    ],
                    cwd=ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            first_bytes = (Path(first) / "email.skill").read_bytes()
            second_bytes = (Path(second) / "email.skill").read_bytes()
            with zipfile.ZipFile(Path(first) / "email.skill") as archive:
                names = archive.namelist()

        self.assertEqual(hashlib.sha256(first_bytes).digest(), hashlib.sha256(second_bytes).digest())
        self.assertTrue(names)
        self.assertTrue(all(name.startswith("email/") for name in names))
        self.assertFalse(any("__pycache__" in name or name.endswith(".pyc") for name in names))

    def test_package_carries_shared_material_and_stays_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as destination:
            subprocess.run(
                [
                    sys.executable,
                    "scripts/package-skill.py",
                    "plugins/writing/skills/email",
                    destination,
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            with zipfile.ZipFile(Path(destination) / "email.skill") as archive:
                names = archive.namelist()
                skill = archive.read("email/SKILL.md").decode("utf-8")

        for shared in ("email/shared/tone.md", "email/shared/format.md"):
            self.assertIn(shared, names)
        self.assertIn("(shared/tone.md)", skill)
        self.assertNotIn("${CLAUDE_", skill)
        self.assertNotIn("../", skill)

    def test_shared_material_carries_no_original_hardcodes(self) -> None:
        shared = "\n".join(path.read_text(encoding="utf-8") for path in (PLUGIN / "shared").rglob("*.md"))

        self.assertTrue(shared.strip())
        for forbidden in ("/Users/", "/home/", "smtp.gmail.com"):
            self.assertNotIn(forbidden, shared)

    def test_every_skill_vendors_the_plugin_shared_material(self) -> None:
        source = {
            path.relative_to(PLUGIN / "shared"): path.read_bytes()
            for path in (PLUGIN / "shared").rglob("*")
            if path.is_file()
        }
        self.assertTrue(source)

        for skill_file in SKILLS.glob("*/SKILL.md"):
            vendored = skill_file.parent / "shared"
            for relative, content in source.items():
                copied = vendored / relative
                self.assertTrue(copied.is_file(), f"{copied} is missing")
                self.assertEqual(copied.read_bytes(), content, f"{copied} is stale")

    def test_no_test_writes_into_the_checkout_it_is_running_from(self) -> None:
        """An interrupted run must not be able to leave this repository half-edited.

        Sixteen tests here used to edit the tree and put it back in a `finally`.
        That holds until the process does not reach the `finally` — Ctrl-C, a
        killed runner, an OOM — and it is also what stops the suite running two
        of them at once. `repository_copy()` costs about 0.15s and removes both.

        Read from the source rather than observed at runtime, because the
        failure mode being prevented is precisely a test that does not finish.
        """

        source = Path(__file__).read_text(encoding="utf-8")
        bodies = re.split(r"\n    def ", source)[1:]
        mutating = re.compile(
            r"\.(write_text|write_bytes|unlink|rename|symlink_to|mkdir)\(|shutil\.(move|rmtree)\("
        )
        # Two rules, both cheap and both aimed at the shape that actually
        # regressed. First: a mutating test has to open some throwaway scope at
        # all — none of the sixteen did. Second: no test may write through an
        # expression rooted at a repository constant, which is how each of them
        # named its target. A test that opens a copy and then writes to ROOT
        # anyway defeats both, and only review catches that.
        scoped = ("repository_copy()", "copy_repository_fixture", "TemporaryDirectory")
        roots = "ROOT|PLUGIN|PLUGINS|SKILLS|DOCS_PLUGIN|README_PATH|SKILLS_README_PATH|CHANGELOG_PATH"
        writes_to_checkout = re.compile(
            rf"\((?:{roots})\s*/[^)]*\)\s*\.(?:write_text|write_bytes|unlink|rename|symlink_to|mkdir)\("
            rf"|\b(?:{roots})\.(?:write_text|write_bytes|unlink|rename|symlink_to)\("
            rf"|shutil\.(?:move|rmtree)\(\s*(?:str\()?(?:{roots})\b"
        )

        unscoped: list[str] = []
        aimed_at_checkout: list[str] = []
        for body in bodies:
            name = body.split("(")[0]
            if not name.startswith("test_") or not mutating.search(body):
                continue
            if not any(marker in body for marker in scoped):
                unscoped.append(name)
            if writes_to_checkout.search(body):
                aimed_at_checkout.append(name)

        self.assertEqual(unscoped, [], "these tests mutate without a throwaway scope; use repository_copy()")
        self.assertEqual(
            aimed_at_checkout, [], "these tests write through a repository path; write to the copy"
        )

    def test_sync_shared_reports_drift(self) -> None:
        with repository_copy() as copied:
            target = copied / "plugins" / "writing" / "skills" / "email" / "shared" / "tone.md"
            target.write_bytes(target.read_bytes() + b"\ndrift\n")
            result = subprocess.run(
                [sys.executable, "scripts/sync-shared.py", "--check"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale vendored copy", result.stderr)

    def test_registry_publishes_exactly_the_tree(self) -> None:
        """The site renders registry.json, so a skill missing from it is unpublished there."""

        registry = json.loads((ROOT / "registry.json").read_text(encoding="utf-8"))
        published = published_skills()

        self.assertEqual(
            {group["id"] for group in registry["groups"]},
            set(published),
            "registry.json and plugins/ disagree about which plugins exist",
        )
        for group in registry["groups"]:
            self.assertEqual(
                sorted(skill["name"] for skill in group["skills"]),
                published[group["id"]],
                f"registry.json and plugins/ disagree about {group['id']}",
            )

    def test_registry_is_reproducible(self) -> None:
        """`--check` is a byte comparison, so a build id or timestamp would break it."""

        rendered = [
            subprocess.run(
                [sys.executable, "scripts/build-registry.py", "--stdout"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            for _ in range(2)
        ]

        self.assertEqual(rendered[0], rendered[1], "two builds of the same tree disagree")
        self.assertEqual(
            rendered[0], (ROOT / "registry.json").read_text(encoding="utf-8"), "registry.json is stale"
        )

    def test_registry_check_reports_an_unrebuilt_catalogue(self) -> None:
        """The committed file is what readers fetch; editing a skill without it is a stale publish."""

        with repository_copy() as copied:
            target = copied / "plugins" / "docs" / "skills" / "readme" / "SKILL.md"
            target.write_text(
                target.read_text(encoding="utf-8").replace("license: MIT", "license: Apache-2.0"),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, "scripts/build-registry.py", "--check"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale", result.stderr)

    def test_registry_refuses_a_skill_no_grouping_files(self) -> None:
        """`notGrouped: bottom` is skills.sh's fallback; publishing under no heading is not one here.

        Dropped from a group with skills left in it, so this is the unfiled-skill
        path rather than the emptied-group one below.
        """

        with repository_copy() as copied:
            path = copied / "skills.sh.json"
            config = json.loads(path.read_text(encoding="utf-8"))
            for group in config["groupings"]:
                if "cleanup" in group["skills"]:
                    group["skills"].remove("cleanup")
            path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "scripts/build-registry.py", "--stdout"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cleanup", result.stderr)
        self.assertIn("no skills.sh.json group", result.stderr)

    def test_registry_refuses_an_emptied_group(self) -> None:
        """An emptied group derives no plugin, and 'spans 0 plugins' names the wrong thing."""

        with repository_copy() as copied:
            path = copied / "skills.sh.json"
            config = json.loads(path.read_text(encoding="utf-8"))
            for group in config["groupings"]:
                if group["title"] == "Docs":
                    group["skills"] = []
            path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "scripts/build-registry.py", "--stdout"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("'Docs' lists no skills", result.stderr)

    def test_registry_carries_a_translation_for_every_published_string(self) -> None:
        """The site renders zh from this file, so a gap is an English string on a Chinese page."""

        registry = json.loads((ROOT / "registry.json").read_text(encoding="utf-8"))
        self.assertEqual(registry["locales"], ["zh"])

        for group in registry["groups"]:
            for locale in registry["locales"]:
                for field in ("title", "description", "summary"):
                    self.assertTrue(
                        group["i18n"][locale][field].strip(),
                        f"group {group['id']} has an empty {locale}.{field}",
                    )
                for skill in group["skills"]:
                    for field in ("description", "overview"):
                        self.assertTrue(
                            skill["i18n"][locale][field].strip(),
                            f"skill {skill['name']} has an empty {locale}.{field}",
                        )

    def test_registry_refuses_a_skill_with_no_translation(self) -> None:
        """Without this the page silently falls back to English for one skill among thirteen."""

        with repository_copy() as copied:
            path = copied / "i18n" / "zh.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            del data["skills"]["ship"]
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "scripts/build-registry.py", "--stdout"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("skill 'ship' has no zh entry", result.stderr)

    def test_registry_refuses_a_translation_for_a_retired_skill(self) -> None:
        """A leftover entry is one the next skill to reuse that name would inherit."""

        with repository_copy() as copied:
            path = copied / "i18n" / "zh.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["skills"]["retired"] = {"description": "x", "overview": "y"}
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "scripts/build-registry.py", "--stdout"],
                cwd=copied,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("skill 'retired' is translated but not published", result.stderr)

    def test_registry_publishes_the_bookmarks_without_claiming_them(self) -> None:
        """Other people's plugins install from this marketplace; the pin is what makes that safe."""

        registry = json.loads((ROOT / "registry.json").read_text(encoding="utf-8"))
        bookmarked = {entry["name"] for entry in registry["bookmarks"]}

        self.assertEqual(bookmarked, bookmarked_plugins())
        # A published plugin appearing here would be this repository's own work
        # presented as somebody else's.
        self.assertFalse(bookmarked & set(published_skills()))
        for entry in registry["bookmarks"]:
            self.assertRegex(entry["sha"], r"\A[0-9a-f]{40}\Z", f"{entry['name']} is not pinned")
            self.assertTrue(entry["url"].startswith("https://"), entry["name"])

    def test_registry_examples_are_the_prompts_ci_scores(self) -> None:
        """A hand-written example drifts; these are the ones the evaluation run uses."""

        registry = json.loads((ROOT / "registry.json").read_text(encoding="utf-8"))
        for group in registry["groups"]:
            for skill in group["skills"]:
                suite = json.loads(
                    (ROOT / "evals" / skill["name"] / "evals.json").read_text(encoding="utf-8")
                )
                self.assertEqual(
                    skill["examples"]["triggers"],
                    [case["prompt"] for case in suite["triggers"]],
                    skill["name"],
                )
                self.assertEqual(
                    skill["examples"]["nonTriggers"],
                    [case["prompt"] for case in suite["non_triggers"]],
                    skill["name"],
                )
                # The boundary is the half a reader most needs and the half a
                # catalogue most often omits.
                self.assertTrue(skill["examples"]["nonTriggers"], f"{skill['name']} publishes no boundary")

    def test_validate_workflow_holds_the_registry_current(self) -> None:
        """Nothing else notices a stale catalogue before a reader fetches it."""

        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/build-registry.py --check", workflow)


if __name__ == "__main__":
    unittest.main()
