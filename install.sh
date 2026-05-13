#!/usr/bin/env bash
# Quorum installer.
# Detects Python 3.11+, creates .venv, installs in editable mode, copies .env,
# and launches the interactive setup wizard.
#
# Usage:  bash install.sh           (or ./install.sh after chmod +x install.sh)

set -euo pipefail

GREEN=$'\033[1;32m'
YELLOW=$'\033[1;33m'
RED=$'\033[1;31m'
DIM=$'\033[2m'
BOLD=$'\033[1m'
RESET=$'\033[0m'

dim()  { printf "%s%s%s\n" "$DIM" "$1" "$RESET"; }
ok()   { printf "  %s%s%s %s\n" "$GREEN" "OK" "$RESET" "$1"; }
warn() { printf "  %s%s%s %s\n" "$YELLOW" "!!" "$RESET" "$1"; }
err()  { printf "  %s%s%s %s\n" "$RED" "XX" "$RESET" "$1" >&2; }

banner() {
  printf "\n"
  printf "%s+------------------------------------------+%s\n" "$GREEN" "$RESET"
  printf "%s|%s  %sQUORUM%s -- consensus reasoning engine    %s|%s\n" "$GREEN" "$RESET" "$BOLD" "$RESET" "$GREEN" "$RESET"
  printf "%s+------------------------------------------+%s\n" "$GREEN" "$RESET"
  dim   "  multi-model council with voting + critique"
  printf "\n"
}

step() {
  printf "\n%s%s%s\n" "$BOLD" "$1" "$RESET"
}

require_python() {
  step "1) Python"
  if ! command -v python3 >/dev/null 2>&1; then
    err "python3 not found. Install Python 3.11+ from https://www.python.org/downloads/"
    exit 1
  fi
  local ver major minor
  ver=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
  IFS=. read -r major minor <<<"$ver"
  if [[ "$major" -lt 3 ]] || { [[ "$major" -eq 3 ]] && [[ "$minor" -lt 11 ]]; }; then
    err "Python 3.11+ required (found $ver)."
    exit 1
  fi
  ok "python3 $ver"
}

create_venv() {
  step "2) Virtualenv"
  if [[ -d .venv ]]; then
    dim "  reusing existing .venv"
  else
    dim "  creating .venv ..."
    python3 -m venv .venv
  fi
  ok ".venv ready  ($(./.venv/bin/python --version 2>&1))"
}

install_pkg() {
  step "3) Dependencies"
  dim "  upgrading pip ..."
  ./.venv/bin/python -m pip install --quiet --upgrade pip
  dim "  installing quorum (editable) ..."
  if ! ./.venv/bin/python -m pip install --quiet -e ".[dev]"; then
    warn "dev extras failed, retrying without them"
    ./.venv/bin/python -m pip install --quiet -e .
  fi
  ok "package installed"
}

prepare_env() {
  step "4) Environment file"
  if [[ -f .env ]]; then
    dim "  .env already exists -- leaving it alone"
  else
    cp .env.example .env
    ok "copied .env.example -> .env"
  fi
}

run_setup() {
  step "5) Interactive setup"
  printf "\n"
  if ! ./.venv/bin/quorum setup; then
    warn "setup did not complete cleanly. Re-run any time:  ./.venv/bin/quorum setup"
  fi
}

footer() {
  printf "\n"
  printf "%s+------------------------------------------+%s\n" "$GREEN" "$RESET"
  printf "%s|%s  %sQuorum is installed.%s                    %s|%s\n" "$GREEN" "$RESET" "$BOLD" "$RESET" "$GREEN" "$RESET"
  printf "%s+------------------------------------------+%s\n" "$GREEN" "$RESET"
  printf "  %sActivate:%s  source .venv/bin/activate\n" "$DIM" "$RESET"
  printf "  %sTry:%s       quorum ask \"what is 2+2?\"\n" "$DIM" "$RESET"
  printf "  %sDoctor:%s    quorum doctor\n\n" "$DIM" "$RESET"
}

main() {
  banner
  require_python
  create_venv
  install_pkg
  prepare_env
  run_setup
  footer
}

main "$@"
