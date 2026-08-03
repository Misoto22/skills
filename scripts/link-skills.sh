#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
AGENT_DESTINATION="${AGENTS_SKILLS_DIR:-${HOME}/.agents/skills}"
CLAUDE_DESTINATION="${CLAUDE_SKILLS_DIR:-${HOME}/.claude/skills}"

mapfile_portable() {
	local line
	while IFS= read -r line; do
		SKILL_FILES+=("$line")
	done < <("$REPO_DIR/scripts/list-skills.sh")
}

link_one() {
	local source_dir="$1"
	local destination_root="$2"
	local skill_name target resolved_target
	skill_name="$(basename "$source_dir")"
	target="$destination_root/$skill_name"
	mkdir -p "$destination_root"

	if [[ -L "$target" ]]; then
		resolved_target="$(
			python3 - "$target" <<'PY'
import sys
from pathlib import Path
print(Path(sys.argv[1]).resolve(strict=False))
PY
		)"
		case "$resolved_target" in
		"$REPO_DIR"/skills/*)
			unlink "$target"
			;;
		*)
			printf 'Conflict: %s is a symlink outside this repository\n' "$target" >&2
			return 1
			;;
		esac
	elif [[ -e "$target" ]]; then
		printf 'Conflict: %s already exists and is not a managed symlink\n' "$target" >&2
		return 1
	fi

	ln -s "$source_dir" "$target"
	printf 'Linked %s -> %s\n' "$target" "$source_dir"
}

SKILL_FILES=()
mapfile_portable
if [[ ${#SKILL_FILES[@]} -eq 0 ]]; then
	printf 'No published skills found\n' >&2
	exit 1
fi

for relative_skill_file in "${SKILL_FILES[@]}"; do
	skill_directory="$REPO_DIR/$(dirname "$relative_skill_file")"
	link_one "$skill_directory" "$AGENT_DESTINATION"
	link_one "$skill_directory" "$CLAUDE_DESTINATION"
done
