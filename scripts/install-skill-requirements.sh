#!/usr/bin/env bash
# Install the dependencies published skills declare for themselves.
#
# Most skills are standard-library only, which is why AGENTS.md asks for
# dependency-free Python unless a reviewed design justifies otherwise. The ones
# that cannot be — astrology needs an ephemeris — carry a requirements.txt in
# their own directory. CI named that one path twice, so the second skill to need
# a dependency would have had to edit a workflow to be tested at all.
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

found=0
while IFS= read -r requirements; do
	found=1
	relative="${requirements#"$REPO_DIR/"}"
	if [ "$LIST_ONLY" -eq 1 ]; then
		echo "$relative"
		continue
	fi
	echo "installing $relative"
	python3 -m pip install --requirement "$requirements"
done < <(find "$REPO_DIR/plugins" -mindepth 4 -maxdepth 4 \
	-path '*/skills/*/requirements.txt' -type f -print | LC_ALL=C sort)

if [ "$found" -eq 0 ] && [ "$LIST_ONLY" -eq 0 ]; then
	echo "no published skill declares a dependency"
fi
