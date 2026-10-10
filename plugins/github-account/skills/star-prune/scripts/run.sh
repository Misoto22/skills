#!/bin/sh
# shellcheck disable=SC2034 # the settings below are read by the sourced bootstrap
# Entry point for star-prune. The shared bootstrap finds or installs Python and
# gh, checks the sign-in and scopes, then runs prune.py.
#
#   sh scripts/run.sh doctor             Report every dependency and the sign-in
#   sh scripts/run.sh doctor --install   Install missing tools without root
#   sh scripts/run.sh <command> ...      scan, apply, restore
#
# apply needs the user scope as well as repo: without it, restore could re-star
# repositories but not put them back into their lists.
set -eu

SKILL_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
# These configure shared/bootstrap.sh, which reads them after the source below.
SKILL_NAME=star-prune
ENTRY="$SKILL_DIR/scripts/prune.py"
USAGE="scan | apply | restore"
OFFLINE_COMMANDS=""
WRITE_COMMANDS="apply restore"
WRITE_SCOPES="user repo|public_repo"

# shellcheck source=/dev/null # the vendored shared/bootstrap.sh is linted on its own
. "$SKILL_DIR/shared/bootstrap.sh"
main "$@"
