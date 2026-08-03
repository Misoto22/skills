#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

find "$REPO_DIR/skills" -mindepth 2 -maxdepth 2 -name SKILL.md -type f -print |
	LC_ALL=C sort |
	sed "s#^$REPO_DIR/##"
