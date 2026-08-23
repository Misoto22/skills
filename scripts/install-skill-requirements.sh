#!/usr/bin/env bash
# Install the dependencies published skills declare for themselves.
#
# Most skills are standard-library only, which is why AGENTS.md asks for
# dependency-free Python unless a reviewed design justifies otherwise. The ones
# that cannot be — anything needing an ephemeris — carry a requirements.txt in
# their own directory. CI named that one path twice, so the second skill to need
# a dependency would have had to edit a workflow to be tested at all.
#
# Installation goes through uv, and deliberately names no interpreter. uv installs
# into an activated virtual environment when there is one and refuses when there
# is not, so a contributor's global packages are never altered by accident. CI has
# no venv and says so once, with UV_SYSTEM_PYTHON in the workflow env.
#
# Says so and exits 0 when no skill declares anything.
#   scripts/install-skill-requirements.sh          install them
#   scripts/install-skill-requirements.sh --list   print the paths and install nothing
#
# `--list` exists so a test can assert this finds every declared file without
# installing anything: a discovery loop nothing checks is one that can quietly
# stop finding the second skill.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
LIST_ONLY=0
if [ "${1-}" = "--list" ]; then
	LIST_ONLY=1
fi

require_uv() {
	if ! command -v uv >/dev/null 2>&1; then
		printf '%s\n' 'uv is required to install skill dependencies.' >&2
		printf '%s\n' 'Install it from https://docs.astral.sh/uv/getting-started/installation/ and retry.' >&2
		exit 2
	fi
}

found=0
while IFS= read -r requirements; do
	if [ "$found" -eq 0 ] && [ "$LIST_ONLY" -eq 0 ]; then
		require_uv
	fi
	found=1
	relative="${requirements#"$REPO_DIR/"}"
	if [ "$LIST_ONLY" -eq 1 ]; then
		echo "$relative"
		continue
	fi
	echo "installing $relative"
	uv pip install --requirement "$requirements"
done < <(find "$REPO_DIR/plugins" -mindepth 4 -maxdepth 4 \
	-path '*/skills/*/requirements.txt' -type f -print | LC_ALL=C sort)

if [ "$found" -eq 0 ] && [ "$LIST_ONLY" -eq 0 ]; then
	echo "no published skill declares a dependency"
fi
