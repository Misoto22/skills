# Shared bootstrap for the github-account skills: finds Python and gh, installs
# them without root when asked, checks the GitHub sign-in and token scopes, then
# runs the skill's Python entry point. Each skill's scripts/run.sh sets these and
# sources this file:
#
#   SKILL_NAME        name shown by doctor
#   ENTRY             absolute path of the skill's Python entry point
#   USAGE             the command list for the usage error
#   OFFLINE_COMMANDS  commands that need neither gh nor a sign-in
#   WRITE_COMMANDS    commands that write to GitHub
#   WRITE_SCOPES      classic-token scopes those commands need; "a|b" means either
#
# Tools land in GITHUB_ACCOUNT_TOOLS_DIR (default ~/.local/share/github-account/bin)
# and are used from there; nothing is written outside it and sudo is never run.
# STAR_LISTS_TOOLS_DIR, the name the first star-lists release documented, is still honoured.
set -eu

TOOLS_DIR=${GITHUB_ACCOUNT_TOOLS_DIR:-${STAR_LISTS_TOOLS_DIR:-"$HOME/.local/share/github-account/bin"}}
PATH="$TOOLS_DIR:$PATH"
export PATH

say() { printf '%s\n' "$*"; }
row() { printf '  %-8s %-8s %s\n' "$1" "$2" "$3"; }
die() { say "error: $*" >&2; exit 1; }

platform() {
  case $(uname -s) in
    Darwin) os=macos ;;
    Linux) os=linux ;;
    MINGW* | MSYS* | CYGWIN*) die "Windows shells are not supported; run this inside WSL" ;;
    *) die "unsupported operating system: $(uname -s)" ;;
  esac
  case $(uname -m) in
    x86_64 | amd64) arch=amd64 ;;
    arm64 | aarch64) arch=arm64 ;;
    *) die "unsupported CPU architecture: $(uname -m)" ;;
  esac
}

# --- Python --------------------------------------------------------------

# On a Mac without the Command Line Tools, /usr/bin/python3 is a stub that opens
# an install dialog instead of running, so it must not be invoked to probe it.
python_is_stub() {
  [ "$(uname -s)" = Darwin ] && [ "$(command -v python3)" = /usr/bin/python3 ] &&
    ! xcode-select -p >/dev/null 2>&1
}

find_python() {
  if command -v python3 >/dev/null 2>&1 && ! python_is_stub &&
    python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    PYTHON="python3"
  elif command -v uv >/dev/null 2>&1; then
    PYTHON="uv run --quiet --no-project --python >=3.9 python3"
  else
    PYTHON=""
  fi
}

# --- downloads ------------------------------------------------------------

fetch() { # fetch URL FILE
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --retry 3 -o "$2" "$1"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$2" "$1"
  else
    die "neither curl nor wget is installed. Install one first, for example: $(package_hint curl)"
  fi
}

package_hint() {
  sudo="sudo "
  [ "$(id -u)" = 0 ] && sudo=""
  if command -v apt-get >/dev/null 2>&1; then say "${sudo}apt-get install -y $1 ca-certificates"
  elif command -v dnf >/dev/null 2>&1; then say "${sudo}dnf install -y $1"
  elif command -v apk >/dev/null 2>&1; then say "${sudo}apk add $1 ca-certificates"
  elif command -v pacman >/dev/null 2>&1; then say "${sudo}pacman -S --noconfirm $1"
  else say "install $1 with your system's package manager"
  fi
}

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d ' ' -f 1
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d ' ' -f 1
  else openssl dgst -sha256 "$1" | sed 's/.*= //'
  fi
}

verify() { # verify FILE EXPECTED_SHA256
  actual=$(sha256_of "$1")
  [ "$actual" = "$2" ] || die "checksum mismatch for $(basename "$1"): expected $2, got $actual"
}

install_gh() {
  platform
  work=$(mktemp -d)
  fetch https://api.github.com/repos/cli/cli/releases/latest "$work/release.json"
  tag=$(sed -n 's/.*"tag_name": *"v\([^"]*\)".*/\1/p' "$work/release.json" | head -n 1)
  [ -n "$tag" ] || die "could not read the latest gh release from api.github.com"
  if [ "$os" = macos ]; then folder="gh_${tag}_macOS_${arch}" asset="$folder.zip"
  else folder="gh_${tag}_linux_${arch}" asset="$folder.tar.gz"; fi
  base="https://github.com/cli/cli/releases/download/v$tag"
  fetch "$base/$asset" "$work/$asset"
  fetch "$base/gh_${tag}_checksums.txt" "$work/checksums.txt"
  verify "$work/$asset" "$(grep " $asset\$" "$work/checksums.txt" | cut -d ' ' -f 1)"
  case $asset in
    *.zip) (cd "$work" && unzip -q "$asset") ;;
    *) tar -xzf "$work/$asset" -C "$work" ;;
  esac
  mkdir -p "$TOOLS_DIR"
  cp "$work/$folder/bin/gh" "$TOOLS_DIR/gh"
  chmod 755 "$TOOLS_DIR/gh"
  rm -rf "$work"
  say "  installed gh $tag into $TOOLS_DIR"
}

install_uv() {
  platform
  case "$os-$arch" in
    macos-amd64) target=x86_64-apple-darwin ;;
    macos-arm64) target=aarch64-apple-darwin ;;
    linux-amd64) target=x86_64-unknown-linux-musl ;;
    linux-arm64) target=aarch64-unknown-linux-musl ;;
  esac
  work=$(mktemp -d)
  asset="uv-$target.tar.gz"
  base=https://github.com/astral-sh/uv/releases/latest/download
  fetch "$base/$asset" "$work/$asset"
  fetch "$base/$asset.sha256" "$work/$asset.sha256"
  verify "$work/$asset" "$(cut -d ' ' -f 1 "$work/$asset.sha256")"
  tar -xzf "$work/$asset" -C "$work"
  mkdir -p "$TOOLS_DIR"
  cp "$work/uv-$target/uv" "$TOOLS_DIR/uv"
  chmod 755 "$TOOLS_DIR/uv"
  rm -rf "$work"
  say "  installed uv into $TOOLS_DIR (it provides Python on first use)"
}

# --- GitHub sign-in -------------------------------------------------------

auth_state() { # sets AUTH_OK, AUTH_LOGIN, AUTH_SCOPES
  AUTH_OK=0 AUTH_LOGIN="" AUTH_SCOPES=""
  command -v gh >/dev/null 2>&1 || return 0
  gh auth status --hostname github.com >/dev/null 2>&1 || return 0
  AUTH_LOGIN=$(gh api user --jq .login 2>/dev/null || true)
  [ -n "$AUTH_LOGIN" ] || return 0
  AUTH_OK=1
  AUTH_SCOPES=$(gh api --include user 2>/dev/null | tr -d '\r' |
    sed -n 's/^[Xx]-[Oo][Aa]uth-[Ss]copes: *//p' | head -n 1)
}

# The scopes in WRITE_SCOPES this token lacks, space-separated. Fine-grained tokens
# send no scope header, so an empty AUTH_SCOPES means "cannot tell", not "missing".
missing_scopes() {
  [ -n "$AUTH_SCOPES" ] || return 0
  granted=$(printf '%s' "$AUTH_SCOPES" | tr ',' '\n' | sed 's/^ *//')
  missing=""
  for need in $WRITE_SCOPES; do
    found=0
    for option in $(printf '%s' "$need" | tr '|' ' '); do
      printf '%s\n' "$granted" | grep -qx "$option" && found=1
    done
    [ "$found" = 1 ] || missing="$missing ${need%%|*}"
  done
  printf '%s' "${missing# }"
}

login_scopes() { printf '%s' "$WRITE_SCOPES" | sed 's/|[^ ]*//g' | tr ' ' ,; }

has_word() { # has_word WORD LIST
  case " $2 " in *" $1 "*) return 0 ;; *) return 1 ;; esac
}

# --- commands -------------------------------------------------------------

doctor() {
  install=0
  [ "${1:-}" = --install ] && install=1
  say "$SKILL_NAME doctor"
  find_python
  if [ -z "$PYTHON" ] && [ "$install" = 1 ]; then install_uv; find_python; fi
  if [ -n "$PYTHON" ]; then
    # shellcheck disable=SC2086 # PYTHON is a command line, deliberately split
    row ok python "$($PYTHON -c 'import sys; print("Python", sys.version.split()[0])')"
  else
    row missing python "no Python 3.9+; fix: sh scripts/run.sh doctor --install"
  fi
  if ! command -v gh >/dev/null 2>&1 && [ "$install" = 1 ]; then install_gh; fi
  if command -v gh >/dev/null 2>&1; then
    row ok gh "$(gh --version | head -n 1)"
  else
    row missing gh "GitHub CLI not found; fix: sh scripts/run.sh doctor --install"
  fi
  auth_state
  if [ "$AUTH_OK" = 1 ]; then
    row ok auth "signed in to github.com as $AUTH_LOGIN${AUTH_SCOPES:+ (scopes: $AUTH_SCOPES)}"
    lacking=$(missing_scopes)
    if [ -n "$lacking" ]; then
      row missing scope "writing needs: $lacking; fix: gh auth refresh --hostname github.com --scopes $(printf '%s' "$lacking" | tr ' ' ,)"
    fi
  elif command -v gh >/dev/null 2>&1; then
    row missing auth "not signed in, or github.com is unreachable; fix: gh auth login --hostname github.com --web --scopes $(login_scopes)"
  fi
  [ -n "$PYTHON" ] && command -v gh >/dev/null 2>&1 && [ "$AUTH_OK" = 1 ] && [ -z "$(missing_scopes)" ]
}

main() {
  [ $# -gt 0 ] || die "usage: sh scripts/run.sh doctor [--install] | $USAGE"
  if [ "$1" = doctor ]; then shift; doctor "$@"; exit $?; fi
  find_python
  [ -n "$PYTHON" ] || die "Python 3.9+ is missing. Run: sh scripts/run.sh doctor --install"
  if ! has_word "$1" "$OFFLINE_COMMANDS"; then
    command -v gh >/dev/null 2>&1 || die "the GitHub CLI is missing. Run: sh scripts/run.sh doctor --install"
    auth_state
    [ "$AUTH_OK" = 1 ] ||
      die "gh is not signed in. Run: gh auth login --hostname github.com --web --scopes $(login_scopes)"
    lacking=$(missing_scopes)
    if has_word "$1" "$WRITE_COMMANDS" && [ -n "$lacking" ]; then
      die "this token cannot make these writes. Run: gh auth refresh --hostname github.com --scopes $(printf '%s' "$lacking" | tr ' ' ,)"
    fi
  fi
  # shellcheck disable=SC2086 # PYTHON is a command line, deliberately split
  exec $PYTHON "$ENTRY" "$@"
}
