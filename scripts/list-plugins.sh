#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

find "$REPO_DIR/plugins" -mindepth 3 -maxdepth 3 -path '*/.claude-plugin/plugin.json' -type f -print |
	LC_ALL=C sort |
	sed "s#^$REPO_DIR/plugins/##" |
	sed 's#/\.claude-plugin/plugin\.json$##'
