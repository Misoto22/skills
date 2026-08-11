#!/usr/bin/env bash
# Print the marketplace name, from the one file that has to declare it.
#
# `<plugin>@<marketplace>` is the string a user types to install, so it reaches
# the bundle's dependencies, the scaffold, the retirement and the install
# workflow. Each of those asks for it here rather than writing it down, the same
# way list-plugins.sh and list-skills.sh derive their names from the tree.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["name"])' \
	"$REPO_DIR/.claude-plugin/marketplace.json"
