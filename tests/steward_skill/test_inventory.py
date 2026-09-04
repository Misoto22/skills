"""The steward's inventory, exercised against real repositories and forged session stores.

Three things this guards, each of which would otherwise fail silently in a sweep:

- A worktree resolving to itself rather than to its primary checkout. The sweep runs
  sync and cleanup once per primary; a linked worktree counted as its own repository is
  swept twice, and the second run finds the first one's deletions.
- A trace that fits nowhere raising instead of counting. Sessions outlive their
  checkouts, scratch repositories live under the temp directory, and a transcript's first
  line can be torn. Any of those ending the inventory ends the sweep.
- Occupancy read from the wrong clock. A worktree with a live process, or one a session
  wrote to inside the window, must come out occupied; one whose sessions are older must
  not, or cleanup can never remove anything.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "dev" / "skills" / "steward" / "scripts" / "inventory.py"
DAY = 86400.0


def load_script():
    spec = importlib.util.spec_from_file_location("steward_inventory", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered before execution: the script's dataclasses resolve their string
    # annotations through sys.modules, and a module loaded by path is not there.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(directory: Path, *args: str) -> str:
    result = subprocess.run(
        [
            "git",
            "-c",
            "user.name=steward",
            "-c",
            "user.email=steward@example.com",
            "-c",
            "init.defaultBranch=main",
            *args,
        ],
        cwd=directory,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def make_repository(path: Path) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q")
    (path / "README.md").write_text("probe\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-q", "-m", "Add readme")
    return path


def transcript(config: Path, name: str, cwd: str | None, age_days: float, *, torn: bool = False) -> Path:
    """A Claude Code transcript: a bookkeeping line first, then an entry carrying cwd."""

    directory = config / "projects" / f"encoded-{name}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.jsonl"
    lines = ["{not json"] if torn else []
    lines.append(json.dumps({"type": "queue-operation", "sessionId": name}))
    if cwd is not None:
        lines.append(json.dumps({"type": "user", "cwd": cwd, "sessionId": name}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    stamp = time.time() - age_days * DAY
    os.utime(path, (stamp, stamp))
    return path


def codex_catalogue(codex_home: Path, rows: list[tuple]) -> Path:
    sqlite_dir = codex_home / "sqlite"
    sqlite_dir.mkdir(parents=True)
    # The summaries database beside it carries no threads and must not be opened.
    (sqlite_dir / "codex-thread-summaries-test.db").write_bytes(b"")
    database = sqlite_dir / "codex-test.db"
    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE TABLE local_thread_catalog ("
        " host_id TEXT NOT NULL, thread_id TEXT NOT NULL, display_title TEXT NOT NULL,"
        " source_created_at REAL NOT NULL, source_updated_at REAL NOT NULL, cwd TEXT,"
        " missing_candidate INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (host_id, thread_id))"
    )
    connection.executemany("INSERT INTO local_thread_catalog VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    connection.commit()
    connection.close()
    return database


def fake_claude(directory: Path, agents: list[dict]) -> Path:
    """A stand-in for the CLI that answers `agents --json` and nothing else."""

    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / "claude"
    payload = json.dumps(agents).replace("'", "'\\''")
    binary.write_text(f"#!/bin/sh\nprintf '%s' '{payload}'\n", encoding="utf-8")
    binary.chmod(0o755)
    return binary


class InventoryTests(unittest.TestCase):
    """One fixture for the class: two repositories, a linked worktree, and every kind of trace."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name).resolve()
        cls.base = base
        cls.config = base / "home" / ".claude"
        cls.codex = base / "home" / ".codex"
        cls.repos = base / "repos"
        cls.alpha = make_repository(cls.repos / "alpha")
        (cls.alpha / "docs").mkdir()
        cls.alpha_wt = cls.repos / "alpha-wt"
        git(cls.alpha, "worktree", "add", "-q", "-b", "feat/probe", str(cls.alpha_wt))
        cls.beta = make_repository(cls.repos / "beta")
        (cls.beta / "scratch.txt").write_text("untracked\n", encoding="utf-8")
        cls.plain = base / "plain"
        cls.plain.mkdir()
        cls.ephemeral = base / "ephemeral"
        make_repository(cls.ephemeral / "scratch")

        transcript(cls.config, "alpha-now", str(cls.alpha), 0.01)
        transcript(cls.config, "alpha-sub", str(cls.alpha / "docs"), 1.0)
        transcript(cls.config, "wt-three-days", str(cls.alpha_wt), 3.0)
        transcript(cls.config, "gone", str(base / "vanished"), 0.1)
        transcript(cls.config, "plain", str(cls.plain), 0.1)
        transcript(cls.config, "scratch", str(cls.ephemeral / "scratch"), 0.1)
        transcript(cls.config, "scratch-gone", str(cls.ephemeral / "vanished-sandbox"), 0.1)
        transcript(cls.config, "old", str(cls.alpha), 40.0)
        transcript(cls.config, "nocwd", None, 0.1, torn=True)

        now = time.time()
        codex_catalogue(
            cls.codex,
            [
                ("local", "t-local", "t", now - 3 * DAY, now - 3 * DAY, str(cls.alpha_wt), 0),
                ("chatgpt:abc:user", "t-cloud", "t", now, now, str(cls.alpha), 0),
                ("local", "t-missing", "t", now, now, str(cls.alpha), 1),
                ("local", "t-old", "t", now - 40 * DAY, now - 40 * DAY, str(cls.alpha), 0),
            ],
        )
        cls.module = load_script()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def run_inventory(self, **overrides) -> dict:
        options = {
            "claude_config": self.config,
            "codex_home": self.codex,
            "roots": [self.repos],
            "since_days": 14,
            "occupied_hours": 24,
            "ignored": [str(self.ephemeral)],
            "claude_binary": None,
        }
        options.update(overrides)
        return self.module.inventory(**options)

    def repository(self, report: dict, primary: Path) -> dict:
        for repository in report["repositories"]:
            if repository["primary"] == str(primary):
                return repository
        self.fail(f"{primary} not in {[r['primary'] for r in report['repositories']]}")

    def worktree(self, repository: dict, path: Path) -> dict:
        for worktree in repository["worktrees"]:
            if os.path.realpath(worktree["path"]) == str(path):
                return worktree
        self.fail(f"{path} not in {[w['path'] for w in repository['worktrees']]}")

    def test_linked_worktree_resolves_to_its_primary(self) -> None:
        report = self.run_inventory()

        self.assertEqual([r["primary"] for r in report["repositories"]], [str(self.alpha), str(self.beta)])
        alpha = self.repository(report, self.alpha)
        self.assertEqual(os.path.realpath(alpha["worktrees"][0]["path"]), str(self.alpha))
        self.assertEqual({w["branch"] for w in alpha["worktrees"]}, {"main", "feat/probe"})
        self.assertEqual(
            {s["id"] for s in self.worktree(alpha, self.alpha)["sessions"]},
            {"alpha-now", "alpha-sub"},
            "a session in a subdirectory belongs to the worktree above it",
        )
        linked = self.worktree(alpha, self.alpha_wt)
        self.assertEqual(
            {(s["client"], s["id"]) for s in linked["sessions"]},
            {("claude-code", "wt-three-days"), ("codex", "t-local")},
        )

    def test_roots_add_repositories_no_session_touched(self) -> None:
        beta = self.repository(self.run_inventory(), self.beta)

        self.assertIsNone(beta["last_activity"])
        self.assertEqual(beta["worktrees"][0]["sessions"], [])
        self.assertEqual(
            beta["worktrees"][0]["dirty"], 1, "the untracked file counts; nothing is deleted on its account"
        )

    def test_traces_that_fit_nowhere_are_counted_not_raised(self) -> None:
        report = self.run_inventory()

        self.assertEqual(
            report["skipped"],
            {"temporary": 2, "missing": 1, "not_git": 1, "unresolved": 1},
            "a deleted sandbox is temporary, not a missing checkout of the person's own",
        )
        self.assertNotIn(str(self.ephemeral / "scratch"), [r["primary"] for r in report["repositories"]])
        alpha_ids = {s["id"] for w in self.repository(report, self.alpha)["worktrees"] for s in w["sessions"]}
        self.assertNotIn("old", alpha_ids, "a transcript older than the window is not a trace")
        self.assertTrue(
            alpha_ids.isdisjoint({"t-cloud", "t-missing", "t-old"}),
            "cloud, missing and old Codex rows are excluded",
        )

    def test_occupancy_follows_the_window(self) -> None:
        report = self.run_inventory()
        alpha = self.repository(report, self.alpha)
        self.assertTrue(self.worktree(alpha, self.alpha)["occupied"])
        self.assertFalse(
            self.worktree(alpha, self.alpha_wt)["occupied"],
            "three days old is not occupied at a 24-hour window",
        )

        widened = self.repository(self.run_inventory(occupied_hours=100), self.alpha)
        self.assertTrue(self.worktree(widened, self.alpha_wt)["occupied"])

    def test_a_live_session_occupies_its_worktree_whatever_its_transcript_says(self) -> None:
        binary = fake_claude(
            self.base / "bin",
            [
                {
                    "id": "live1",
                    "sessionId": "live-1",
                    "cwd": str(self.alpha_wt),
                    "kind": "interactive",
                    "pid": 4242,
                },
                {
                    "id": "bg",
                    "sessionId": "bg-1",
                    "cwd": str(self.alpha),
                    "kind": "background",
                    "state": "blocked",
                    "startedAt": (time.time() - 60 * DAY) * 1000,
                },
                {"id": "nocwd"},
            ],
        )
        report = self.run_inventory(claude_binary=str(binary))

        self.assertEqual(report["sources"]["claude_code"]["live"], 1)
        linked = self.worktree(self.repository(report, self.alpha), self.alpha_wt)
        self.assertTrue(linked["occupied"])
        self.assertIn(("live-1", True), {(s["id"], s["live"]) for s in linked["sessions"]})
        self.assertEqual(self.run_inventory()["sources"]["claude_code"]["live"], "unavailable")

    def test_no_codex_catalogue_is_reported_not_raised(self) -> None:
        report = self.run_inventory(codex_home=self.base / "nowhere")

        self.assertEqual(report["sources"]["codex"]["threads"], "unavailable")
        self.assertEqual(len(report["repositories"]), 2)

    def test_default_ignore_list_is_the_temp_directory(self) -> None:
        self.assertIn(os.path.realpath(tempfile.gettempdir()), self.module.default_ignored())

    def test_cli_prints_one_json_document(self) -> None:
        env = {
            **os.environ,
            "HOME": str(self.base / "home"),
            "CLAUDE_CONFIG_DIR": str(self.config),
            "CODEX_HOME": str(self.codex),
        }
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--no-live",
                "--since",
                "14",
                f"--roots={self.repos}",
                "--ignore-under",
                str(self.ephemeral),
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["since_days"], 14)
        self.assertEqual([r["primary"] for r in report["repositories"]], [str(self.alpha), str(self.beta)])
        self.assertEqual(report["sources"]["claude_code"]["live"], "unavailable")


if __name__ == "__main__":
    unittest.main()
