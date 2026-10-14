"""The opt-in background service: a per-user launchd agent that reruns the alignment.

Installing copies this ``scripts/`` directory to a stable place — a plugin's cache path
changes with every update, and an agent pointing into it would break on the next one —
and writes ``~/Library/LaunchAgents/<LABEL>.plist`` running the copy's ``merge.py
--service-run`` when the session index or the environments file changes, and every five
minutes in case a change happened deeper than launchd watches. Installing again upgrades
the copy and reloads the agent. ``launchctl`` is reached through an injectable runner,
so tests never touch the real one.
"""

from __future__ import annotations

import json
import os
import plistlib
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import atomic
import environments_sync
import lifecycle
import local_storage
from index_tree import CONFIG_DIR_ENV, SESSIONS_ROOT_ENV

LABEL = "local.skills.reunite"
INSTALL_DIR = "Library/Application Support/reunite-service"
LOG_FILE = "Library/Logs/reunite-service.log"
STATE_NAME = ".session-merge-service.json"
LOCK_NAME = ".session-merge-service.lock"
START_INTERVAL = 300
THROTTLE_INTERVAL = 30
# launchd starts an agent with PATH=/usr/bin:/bin:/usr/sbin:/sbin, whose python3 is too
# old for these scripts, so the interpreter that installed the agent goes first.
SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
CARRIED_ENV = (SESSIONS_ROOT_ENV, CONFIG_DIR_ENV, local_storage.STORE_ENV, environments_sync.APP_DIR_ENV)

Runner = Callable[[list[str]], subprocess.CompletedProcess]


def launchctl(argv: list[str]) -> subprocess.CompletedProcess:
    """Run one launchctl command, capturing its output instead of letting it reach the terminal."""
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def plist_path() -> Path:
    """Where the agent definition lives."""
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def install_dir() -> Path:
    """The stable directory the scripts are copied to."""
    return Path.home() / INSTALL_DIR


def log_path() -> Path:
    """Where launchd sends the agent's output: one line per run."""
    return Path.home() / LOG_FILE


def installed() -> bool:
    """Whether the agent is installed — the condition --undo refuses under."""
    return plist_path().exists()


def python_dir() -> Path:
    """The directory whose ``python3`` is the interpreter running this, for the agent's PATH."""
    here = Path(sys.executable).parent
    if (here / "python3").exists():
        return here
    found = shutil.which("python3")
    return Path(found).parent if found else here


def render_plist(script: Path, watched: list[Path], interpreter_dir: Path, log: Path) -> bytes:
    """The agent definition: run ``script --service-run`` on changes, at load, and every five minutes."""
    env = {"PATH": f"{interpreter_dir}:{SYSTEM_PATH}"}
    env.update({name: os.environ[name] for name in CARRIED_ENV if os.environ.get(name)})
    agent = {
        "Label": LABEL,
        "ProgramArguments": ["/usr/bin/env", "python3", str(script), "--service-run"],
        "WatchPaths": [str(path) for path in watched],
        "StartInterval": START_INTERVAL,
        "ThrottleInterval": THROTTLE_INTERVAL,
        "RunAtLoad": True,
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
        "EnvironmentVariables": env,
        "ProcessType": "Background",
    }
    return plistlib.dumps(agent)


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _loaded(runner: Runner) -> bool:
    return runner(["launchctl", "print", f"{_domain()}/{LABEL}"]).returncode == 0


def _copy_scripts(scripts: Path) -> Path:
    """Replace the stable copy with ``scripts``, staged beside it so a failure leaves the old one."""
    target = install_dir() / "scripts"
    staging = target.with_name("scripts.new")
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(scripts, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if target.exists():
        retired = target.with_name("scripts.old")
        shutil.rmtree(retired, ignore_errors=True)
        target.rename(retired)
        staging.rename(target)
        shutil.rmtree(retired)
    else:
        staging.rename(target)
    return target


def install(
    root: Path, scripts: Path, runner: Runner = launchctl, interpreter_dir: Path | None = None
) -> int:
    """Copy the scripts, write the agent and load it, replacing any earlier install. Returns the status."""
    if not (root / lifecycle.BASELINE_NAME).exists():
        print("Run merge.py --apply once first, so the counts it writes have been seen and agreed to;")
        print("the service only keeps an alignment you have already made.")
        return 1
    target = _copy_scripts(scripts.resolve())
    watched = [root, environments_sync.presets_path(root)]
    plist = plist_path()
    plist.parent.mkdir(parents=True, exist_ok=True)
    log_path().parent.mkdir(parents=True, exist_ok=True)
    content = render_plist(target / "merge.py", watched, interpreter_dir or python_dir(), log_path())
    atomic.write_bytes(plist, content, mode=0o644)
    if _loaded(runner):
        runner(["launchctl", "bootout", f"{_domain()}/{LABEL}"])
    loaded = runner(["launchctl", "bootstrap", _domain(), str(plist)])
    if loaded.returncode != 0:
        print(f"launchctl bootstrap failed: {(loaded.stderr or loaded.stdout).strip()}")
        return 1
    print(f"Installed {LABEL}: runs {target / 'merge.py'} --service-run")
    print(f"  on changes to {root} and {watched[1].name}, and every {START_INTERVAL // 60} minutes.")
    print(f"  Log: {log_path()}   Status: merge.py --service-status   Remove: merge.py --uninstall-service")
    return 0


def uninstall(runner: Runner = launchctl) -> int:
    """Unload the agent and remove its definition and the copied scripts. Returns the status."""
    runner(["launchctl", "bootout", f"{_domain()}/{LABEL}"])
    plist_path().unlink(missing_ok=True)
    shutil.rmtree(install_dir(), ignore_errors=True)
    print(f"Uninstalled {LABEL}; nothing runs in the background any more.")
    return 0


def status(root: Path, runner: Runner = launchctl) -> int:
    """Print whether the agent is installed and loaded, and how its last run went."""
    print(
        f"{LABEL}: {'installed' if installed() else 'not installed'}, "
        f"{'loaded' if _loaded(runner) else 'not loaded'}"
    )
    try:
        state = json.loads((root / STATE_NAME).read_text())
    except (OSError, ValueError):
        print("  no run recorded yet")
        return 0
    print(f"  last run {state.get('lastRun', 'unknown')}: {state.get('result', 'unknown')}")
    print(f"  log {log_path()}")
    return 0


def add_arguments(parser) -> None:
    """The command-line flags this module owns."""
    parser.add_argument("--install-service", action="store_true", help="install or upgrade the launchd agent")
    parser.add_argument(
        "--uninstall-service", action="store_true", help="unload and remove the launchd agent"
    )
    parser.add_argument("--service-status", action="store_true", help="show the agent and its last run")
    parser.add_argument(
        "--service-run", action="store_true", help="one background pass, as the agent runs it"
    )
