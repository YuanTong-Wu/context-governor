#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

python3 tools/context/context_integrity_check.py --root "$ROOT"
python3 tools/context/recursive_entry_detector.py --root "$ROOT"
python3 tools/context/build_index_views.py --root "$ROOT"
python3 tools/context/build_startup_bundle.py --root "$ROOT"
python3 tools/context/startup_budget_test.py --root "$ROOT"
if [[ -x tools/dev/run_dev_checks.sh ]]; then
  bash tools/dev/run_dev_checks.sh --root "$ROOT"
fi
