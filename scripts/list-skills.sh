#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

find "$REPO_DIR/plugins" -mindepth 4 -maxdepth 4 -path '*/skills/*/SKILL.md' -type f -print |
	LC_ALL=C sort |
	sed "s#^$REPO_DIR/##"
