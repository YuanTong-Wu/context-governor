#!/usr/bin/env bash
set -uo pipefail

ROOT="$(pwd)"
if [ "${1:-}" = "--root" ]; then
  ROOT="$2"
  shift 2
fi
ROOT="$(cd "$ROOT" && pwd)"
PYTHON="${PYTHON:-python3}"

cd "$ROOT" || exit 1
mkdir -p var/dev_change_control_2026_06_24

status=0

run_step() {
  name="$1"
  shift
  echo "[dev-check] $name"
  "$@"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "[dev-check] $name failed with $rc"
    status=1
  fi
}

run_step preflight "$PYTHON" tools/dev/preflight_change.py --root "$ROOT" "$@"
run_step impact "$PYTHON" tools/dev/impact_check.py --root "$ROOT" "$@"
run_step schema "$PYTHON" tools/dev/schema_compat_check.py --root "$ROOT" "$@"
run_step paths "$PYTHON" tools/dev/path_consistency_check.py --root "$ROOT" "$@"
run_step invariants "$PYTHON" tools/dev/invariant_check.py --root "$ROOT" "$@"
run_step regressions "$PYTHON" tools/dev/regression_check.py --root "$ROOT" "$@"
run_step summary "$PYTHON" tools/dev/change_summary.py --root "$ROOT" "$@"

echo "[dev-check] summary: var/dev_change_control_2026_06_24/CHANGE_SUMMARY.md"
exit "$status"
