from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"
PLUGIN = PLUGINS / "writing"
SKILLS = PLUGIN / "skills"
DOCS_PLUGIN = PLUGINS / "docs"
README_PATH = ROOT / "README.md"
SKILLS_README_PATH = SKILLS / "README.md"
PLUGIN_PATH = PLUGIN / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = ROOT / ".claude-plugin" / "marketplace.json"
LINK_SCRIPT = ROOT / "scripts" / "link-skills.sh"


class RepositoryContractTests(unittest.TestCase):
    def test_only_published_tree_is_in_plugin_manifest(self) -> None:
        plugin = json.loads(PLUGIN_PATH.read_text(encoding="utf-8"))

        self.assertEqual(plugin["skills"], ["./skills/email", "./skills/tempering"])
        self.assertEqual(plugin["author"]["name"], "skills contributors")
        self.assertNotIn("drafts", json.dumps(plugin))
        self.assertNotIn("deprecated", json.dumps(plugin))

    def test_marketplace_registers_the_writing_plugin(self) -> None:
        marketplace = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(marketplace["name"], "misoto22")
        self.assertEqual(marketplace["metadata"]["pluginRoot"], "./plugins")
        self.assertEqual(
            {entry["name"]: entry["source"] for entry in marketplace["plugins"]},
            {"writing": "./plugins/writing", "docs": "./plugins/docs"},
        )

    def test_every_published_skill_is_registered(self) -> None:
        published = {"writing": ["email", "tempering"], "docs": ["readme"]}
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

    def test_docs_plugin_declares_the_readme_skill(self) -> None:
        plugin = json.loads((DOCS_PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))

        self.assertEqual(plugin["name"], "docs")
        self.assertEqual(plugin["skills"], ["./skills/readme"])
        self.assertEqual(plugin["version"], "0.3.0")
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

        self.assertEqual(
            result.stdout,
            "plugins/docs/skills/readme/SKILL.md\n"
            "plugins/writing/skills/email/SKILL.md\n"
            "plugins/writing/skills/tempering/SKILL.md\n",
        )

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

        self.assertEqual(plugin["version"], "0.3.0")
        self.assertIn('version: "0.3.0"', skill)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("actions/checkout@v7", workflow)
        self.assertIn("actions/setup-python@v7", workflow)
        self.assertIn("actions/setup-node@v7", workflow)
        self.assertIn("skills@1.5.20", workflow)
        self.assertIn("@anthropic-ai/claude-code@2.1.220", workflow)
        self.assertIn('python-version: ["3.11", "3.13"]', workflow)
        self.assertIn("astral-sh/ruff-action@v3", workflow)
        self.assertIn('version: "0.14.6"', workflow)
        self.assertIn("shellcheck scripts/*.sh", workflow)

    def test_release_workflow_packages_every_skill_on_tag_push(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

        self.assertIn('tags: ["v*"]', workflow)
        self.assertIn("permissions:\n  contents: write", workflow)
        self.assertIn("actions/checkout@v7", workflow)
        self.assertIn("actions/setup-python@v7", workflow)
        self.assertIn("scripts/list-skills.sh", workflow)
        self.assertIn("scripts/package-skill.py", workflow)
        self.assertIn("dist/*.skill", workflow)

    def test_install_workflow_covers_every_supported_route(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "install.yml").read_text(encoding="utf-8")

        for route in (
            "claude plugin install writing@misoto22",
            "codex plugin add writing@misoto22",
            "claude plugin install docs@misoto22",
            "codex plugin add writing@misoto22",
            "codex plugin add docs@misoto22",
            "npx --yes skills@1.5.20 add",
            "scripts/package-skill.py",
        ):
            self.assertIn(route, workflow)
        self.assertIn("@anthropic-ai/claude-code@2.1.220", workflow)
        self.assertIn("@openai/codex@0.145.0", workflow)
        self.assertEqual(workflow.count("scripts/verify-install.py"), 4)

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
        subprocess.run(
            [
                sys.executable,
                "scripts/verify-install.py",
                str(PLUGINS),
                "--expect",
                "email",
                "--expect",
                "tempering",
                "--expect",
                "readme",
            ],
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

    def test_version_bump_round_trips_without_drift(self) -> None:
        config = json.loads((ROOT / ".version-bump.json").read_text(encoding="utf-8"))
        declared = [entry["path"] for entry in config["json"]] + config["text"]
        before = {path: (ROOT / path).read_bytes() for path in declared}

        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, "scripts/bump-version.py", *args],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        try:
            self.assertEqual(run("9.9.9").returncode, 0)
            self.assertIn("current version: 9.9.9", run("--check").stdout)
            for path in declared:
                self.assertNotEqual((ROOT / path).read_bytes(), before[path], path)
            self.assertEqual(run("0.3.0").returncode, 0)
        finally:
            for path, content in before.items():
                (ROOT / path).write_bytes(content)

        self.assertNotEqual(run("bad-version").returncode, 0)

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

    def test_sync_shared_reports_drift(self) -> None:
        target = SKILLS / "email" / "shared" / "tone.md"
        original = target.read_bytes()
        target.write_bytes(original + b"\ndrift\n")
        try:
            result = subprocess.run(
                [sys.executable, "scripts/sync-shared.py", "--check"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("stale vendored copy", result.stderr)
        finally:
            target.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
