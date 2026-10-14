"""The environments step of a run: read the presets file, report the plan, and write it.

The app keeps ``ccd-session-presets.json`` in its own directory, beside the session
index; ``CLAUDE_DESKTOP_APP_DIR`` names that directory where it is elsewhere. The file
is replaced in one rename, keeping its mode, after its original is gzipped under the
backup directory and recorded for ``--undo``. The app writes the same file, so it is
read again just before the rename and left alone if it moved in between.
"""

from __future__ import annotations

import gzip
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import atomic
import environments
from environments import EnvBaseline, EnvironmentsError, EnvPlan
from manifest import BACKUP_DIR, environments_records, write_manifest

APP_DIR_ENV = "CLAUDE_DESKTOP_APP_DIR"
PRESETS_NAME = "ccd-session-presets.json"
BASELINE_NAME = ".session-merge-environments.json"


@dataclass(frozen=True)
class Step:
    """The presets file as read, and the plan made from it."""

    path: Path
    raw: bytes
    plan: EnvPlan


def presets_path(root: Path) -> Path:
    """The environments file: in CLAUDE_DESKTOP_APP_DIR, else beside the session index."""
    base = os.environ.get(APP_DIR_ENV)
    return (Path(base).expanduser() if base else root.parent) / PRESETS_NAME


def encode(document: dict) -> bytes:
    """Serialize as the app does: tab-indented, non-ASCII kept, no trailing newline."""
    return json.dumps(document, indent="\t", ensure_ascii=False).encode()


def load_baseline(root: Path) -> EnvBaseline | None:
    """The previous write's record, or None before the first one."""
    try:
        data = json.loads((root / BASELINE_NAME).read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise EnvironmentsError(f"unreadable {BASELINE_NAME}: {error}") from error
    held, deleted = (data.get("held"), data.get("deleted")) if isinstance(data, dict) else (None, None)
    if not isinstance(held, dict) or not isinstance(deleted, dict):
        raise EnvironmentsError(f"{BASELINE_NAME} is not a baseline this script wrote")
    return EnvBaseline(
        held={a: [i for i in ids if isinstance(i, str)] for a, ids in held.items() if isinstance(ids, list)},
        deleted={i: when for i, when in deleted.items() if isinstance(when, int)},
    )


def save_baseline(root: Path, baseline: EnvBaseline) -> None:
    """Record what the file holds now; an unchanged record is not rewritten."""
    path = root / BASELINE_NAME
    payload = {"held": dict(sorted(baseline.held.items())), "deleted": dict(sorted(baseline.deleted.items()))}
    content = json.dumps(payload, separators=(",", ":")).encode()
    if not path.exists() or path.read_bytes() != content:
        atomic.write_bytes(path, content)


def plan_step(root: Path, targets: list[str], everyone: bool, now: int) -> Step | None:
    """Read the file and plan its alignment; None when the app has written no file yet.

    With ``everyone``, an account that holds presets but has no index directory is a
    target too.
    """
    path = presets_path(root)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    try:
        document = json.loads(raw)
    except ValueError as error:
        raise EnvironmentsError(f"{path.name} is not readable JSON: {error}") from error
    if everyone:
        targets = sorted(set(targets) | set(environments.entries_of(document)))
    return Step(path, raw, environments.plan_environments(document, targets, load_baseline(root), now))


def report(step: Step) -> None:
    """Print the file, any frozen account, and the counts --apply would write."""
    plan = step.plan
    print(f"\nEnvironments {step.path}")
    print(f"  {len(plan.union)} presets after aligning; {len(plan.baseline.deleted)} deletions kept out")
    for account in plan.frozen:
        print(f"  account {account} held presets at the last run and holds none now — left as it is")
    added = sum(c.added for c in plan.changes)
    updated = sum(c.updated for c in plan.changes)
    removed = sum(c.removed for c in plan.changes)
    print(f"environments: {added} to add, {updated} to update, {removed} removed")


def _back_up(root: Path, path: Path) -> dict[str, object] | None:
    """Keep the file's original before the first write; a later write keeps that one."""
    if environments_records(root):
        return None
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = root / BACKUP_DIR / f"ccd-session-presets-{stamp}.json.gz"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(gzip.compress(path.read_bytes()))
    return {"backup": backup.name, "file": str(path.resolve()), "mtime": path.stat().st_mtime}


def apply_step(root: Path, step: Step) -> None:
    """Write the aligned file and its baseline, unless the app changed the file since it was read."""
    if step.plan.changed:
        if step.path.read_bytes() != step.raw:
            raise EnvironmentsError(f"{step.path.name} changed while this run was planning; rerun")
        record = _back_up(root, step.path)
        if record:
            write_manifest(root, [], [], environments=record)
        atomic.write_bytes(step.path, encode(step.plan.document))
    save_baseline(root, step.plan.baseline)


def run(root: Path, targets: list[str], everyone: bool, apply: bool) -> int:
    """Report the environments step, and with ``apply`` write it. Returns the exit status."""
    try:
        step = plan_step(root, targets, everyone, int(time.time() * 1000))
        if step is None:
            print(f"\nEnvironments: no environments file at {presets_path(root)} yet; nothing to align.")
            return 0
        report(step)
        if apply:
            apply_step(root, step)
    except (EnvironmentsError, OSError) as error:
        print(f"ENVIRONMENTS NOT ALIGNED: {error}")
        return 1
    if apply and step.plan.changed:
        holding = sum(1 for ids in step.plan.baseline.held.values() if ids == step.plan.union)
        print(f"Environments aligned: {len(step.plan.union)} presets in {holding} account(s).")
    return 0


def undo(root: Path, records: list[dict[str, object]]) -> None:
    """Put back the file as it was before the first recorded write, and forget the baseline.

    Exits, writing nothing, when the backup was taken from a different file.
    """
    check_undo(root, records)
    target = presets_path(root)
    try:
        content = gzip.decompress((root / BACKUP_DIR / str(records[0]["backup"])).read_bytes())
    except (OSError, EOFError, gzip.BadGzipFile):
        print("  environments backup is missing; the environments file was not restored.")
        return
    mtime = records[0].get("mtime")
    atomic.write_bytes(target, content, mtime if isinstance(mtime, (int, float)) else None)
    (root / BASELINE_NAME).unlink(missing_ok=True)
    print(f"Restored the environments file {target}.")


def check_undo(root: Path, records: list[dict[str, object]]) -> None:
    """Exit now if --undo could not restore the environments file, before anything is undone."""
    target = presets_path(root)
    if records and Path(str(records[0]["file"])).resolve() != target.resolve():
        sys.exit(
            f"The environments backup was taken from {records[0]['file']}, but {APP_DIR_ENV} "
            f"now points at {target}. Point it back and rerun."
        )
