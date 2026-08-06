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

    # shared/ is vendored into the skill by sync-shared.py, so the archive is
    # self-contained with no path rewriting; refuse to ship a stale copy.
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync-shared.py"), "--check"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate-repository.py"), "--skip-tests"],
        cwd=ROOT,
        check=True,
    )

    output_directory = destination.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    output = output_directory / f"{source.name}.skill"
    files = sorted(
        path
        for path in source.rglob("*")
        if path.is_file() and not _excluded(path.relative_to(source))
    )
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for file_path in files:
            relative = file_path.relative_to(source)
            info = zipfile.ZipInfo(f"{source.name}/{relative.as_posix()}", ARCHIVE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, file_path.read_bytes())
    return output


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
