#!/usr/bin/env python3
"""Create a deterministic .skill archive from one published skill."""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {"__pycache__", ".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
ARCHIVE_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
REWRITTEN_SUFFIXES = {".md", ".txt", ".yaml", ".yml"}

# In the repository a skill reaches its plugin's shared/ directory by climbing out
# of skills/<name>/. An unpacked .skill has no plugin above it, so the archive
# carries its own copy of shared/ beside SKILL.md and the references are rebased.
SHARED_SOURCE_PREFIX = "${CLAUDE_SKILL_DIR}/../../shared/"
SHARED_ARCHIVE_PREFIX = "${CLAUDE_SKILL_DIR}/shared/"


def package_skill(skill_path: Path, destination: Path) -> Path:
    source = skill_path.expanduser().resolve()
    plugins_root = (ROOT / "plugins").resolve()
    skills_root = source.parent
    if (
        not source.is_dir()
        or skills_root.name != "skills"
        or skills_root.parent.parent != plugins_root
    ):
        raise ValueError("skill path must be a direct published child of plugins/<plugin>/skills/")
    if not (source / "SKILL.md").is_file():
        raise ValueError("skill is missing SKILL.md")
    nested = [path for path in source.rglob("SKILL.md") if path != source / "SKILL.md"]
    if nested:
        raise ValueError("nested SKILL.md files are not allowed in one package")

    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate-repository.py"), "--skip-tests"],
        cwd=ROOT,
        check=True,
    )

    shared_root = skills_root.parent / "shared"
    if (source / "shared").exists():
        raise ValueError("a skill may not define its own shared/; it is reserved for the plugin copy")

    output_directory = destination.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    output = output_directory / f"{source.name}.skill"
    members = [(path, path.relative_to(source)) for path in source.rglob("*")]
    if shared_root.is_dir():
        members += [
            (path, Path("shared") / path.relative_to(shared_root))
            for path in shared_root.rglob("*")
        ]
    entries = sorted(
        (relative.as_posix(), path)
        for path, relative in members
        if path.is_file() and not _excluded(relative)
    )
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for relative, file_path in entries:
            info = zipfile.ZipInfo(f"{source.name}/{relative}", ARCHIVE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, _archive_bytes(file_path))
    return output


def _archive_bytes(file_path: Path) -> bytes:
    """Return the packaged bytes, rebasing shared/ references for a standalone skill."""

    raw = file_path.read_bytes()
    if file_path.suffix not in REWRITTEN_SUFFIXES:
        return raw
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        return raw
    if SHARED_SOURCE_PREFIX not in text:
        return raw
    return text.replace(SHARED_SOURCE_PREFIX, SHARED_ARCHIVE_PREFIX).encode("utf-8")


def _excluded(relative: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in relative.parts) or relative.suffix in EXCLUDED_SUFFIXES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    try:
        output = package_skill(args.skill, args.destination)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"skill packaging failed: {error}", file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
