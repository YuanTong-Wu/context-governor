#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

python3 tools/context/context_integrity_check.py --root "$ROOT"
python3 tools/context/recursive_entry_detector.py --root "$ROOT"
python3 tools/context/build_index_views.py --root "$ROOT"
python3 tools/context/build_startup_bundle.py --root "$ROOT"
python3 tools/context/startup_budget_test.py --root "$ROOT"

python3 - "$ROOT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
state = json.loads((root / "context/TASK_STATE.json").read_text(encoding="utf-8"))
if str(state.get("holdout_status", "")).upper() != "LOCKED":
    raise SystemExit("holdout must remain LOCKED")
print("context pre-commit checks passed")
PY
