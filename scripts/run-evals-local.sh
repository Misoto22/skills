#!/usr/bin/env bash
# Score a skill suite locally through the scoped LiteLLM gateway before pushing.
#
# This intentionally uses a short-lived uv virtual environment so the preflight
# neither alters the contributor's global Python packages nor stores a key in
# the repository. Export the key from the approved secret manager first.
#
#   LITELLM_EVALS_API_KEY=... bash scripts/run-evals-local.sh <skill>
#   LITELLM_EVALS_API_KEY=... bash scripts/run-evals-local.sh
#
# EVALS_SPLIT selects which cases run: tuning drives an edit, holdout gates it,
# all is the default and is what CI scores. See evals/ITERATION.md.
#
#   LITELLM_EVALS_API_KEY=... EVALS_SPLIT=tuning  bash scripts/run-evals-local.sh email
#   LITELLM_EVALS_API_KEY=... EVALS_SPLIT=holdout bash scripts/run-evals-local.sh email
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
BASE_URL="${LITELLM_EVALS_BASE_URL:-https://llm-evals.misoto22.com/v1}"
SKILL="${1:-}"
SPLIT="${EVALS_SPLIT:-all}"

usage() {
	printf 'Usage: %s [skill]\n' "${0##*/}"
}

if [ "$#" -gt 1 ]; then
	usage >&2
	exit 2
fi

if [ "$SKILL" = "--help" ] || [ "$SKILL" = "-h" ]; then
	usage
	exit 0
fi

case "$SPLIT" in
tuning | holdout | all) ;;
*)
	printf 'EVALS_SPLIT must be tuning, holdout, or all; got %s\n' "$SPLIT" >&2
	exit 2
	;;
esac

if [ -z "${LITELLM_EVALS_API_KEY:-}" ]; then
	printf '%s\n' 'LITELLM_EVALS_API_KEY is required; export it from the approved secret manager.' >&2
	exit 2
fi

if ! command -v uv >/dev/null 2>&1; then
	printf '%s\n' 'uv is required to run the preflight.' >&2
	printf '%s\n' 'Install it from https://docs.astral.sh/uv/getting-started/installation/ and retry.' >&2
	exit 2
fi

VENV_DIR="$(mktemp -d "${TMPDIR:-/tmp}/skills-evals.XXXXXX")"
cleanup() {
	rm -rf "$VENV_DIR"
}
trap cleanup EXIT

uv venv --quiet "$VENV_DIR"
uv pip install --quiet --python "$VENV_DIR/bin/python" "$(python3 "$REPO_DIR/scripts/ci-pins.py" spec openai)"

export LITELLM_EVALS_BASE_URL="$BASE_URL"

if [ -n "$SKILL" ]; then
	"$VENV_DIR/bin/python" "$REPO_DIR/scripts/run-evals.py" --run "$SKILL" --split "$SPLIT"
	"$VENV_DIR/bin/python" "$REPO_DIR/scripts/run-evals.py" --run-behaviors "$SKILL" --split "$SPLIT"
else
	"$VENV_DIR/bin/python" "$REPO_DIR/scripts/run-evals.py" --run --split "$SPLIT"
	"$VENV_DIR/bin/python" "$REPO_DIR/scripts/run-evals.py" --run-behaviors --split "$SPLIT"
fi
