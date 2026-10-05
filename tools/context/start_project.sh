#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT_ID=""
PROJECT_NAME=""
PROJECT_ROOT=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --project-root)
      PROJECT_ROOT="$2"
      shift 2
      ;;
    --project-name)
      PROJECT_NAME="$2"
      shift 2
      ;;
    --project-id|--project)
      PROJECT_ID="$2"
      shift 2
      ;;
    *)
      if [ -z "$PROJECT_ID" ]; then
        PROJECT_ID="$1"
      elif [ -z "$PROJECT_NAME" ]; then
        PROJECT_NAME="$1"
      else
        echo "[start-project] unknown argument: $1" >&2
        exit 2
      fi
      shift
      ;;
  esac
done

ROOT="$(cd "$ROOT" && pwd)"
PROJECT_ID="${PROJECT_ID:-default}"
PYTHON="${PYTHON:-python3}"

cd "$ROOT" || exit 1

# A registered project keeps its stored root and name unless they are given here.
INIT_ARGS=(--root "$ROOT" --project-id "$PROJECT_ID" --activate)
if [ -n "$PROJECT_ROOT" ]; then
  INIT_ARGS+=(--project-root "$PROJECT_ROOT")
fi
if [ -n "$PROJECT_NAME" ]; then
  INIT_ARGS+=(--project-name "$PROJECT_NAME")
fi
"$PYTHON" tools/context/project/init_project_context.py "${INIT_ARGS[@]}"

"$PYTHON" tools/context/build_file_index.py --root "$ROOT" --project-id "$PROJECT_ID"
"$PYTHON" tools/context/build_runner_index.py --root "$ROOT" --project-id "$PROJECT_ID"
"$PYTHON" tools/context/build_case_index.py --root "$ROOT" --project-id "$PROJECT_ID"
"$PYTHON" tools/context/build_evidence_index.py --root "$ROOT" --project-id "$PROJECT_ID"
"$PYTHON" tools/context/build_gap_index.py --root "$ROOT" --project-id "$PROJECT_ID"
"$PYTHON" tools/context/build_index_views.py --root "$ROOT" --project-id "$PROJECT_ID"
"$PYTHON" tools/context/build_startup_bundle.py --root "$ROOT" --project-id "$PROJECT_ID"
"$PYTHON" tools/context/startup_budget_test.py --root "$ROOT" --project-id "$PROJECT_ID"
"$PYTHON" tools/context/context_integrity_check.py --root "$ROOT"

"$PYTHON" - "$ROOT" "$PROJECT_ID" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
project_id = sys.argv[2]
sys.path.insert(0, str(root / "tools/context"))
from governor_common import get_project, project_abs_path, project_control_path

project = get_project(root, project_id)
state_path = project_abs_path(root, project, project["state_path"])
state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
bundle = project_control_path(root, project, project["startup_bundle_path"])
try:
    bundle_rel = bundle.relative_to(root)
except ValueError:
    bundle_rel = bundle

print(f"PROJECT_ID={project_id}")
print(f"STARTUP_BUNDLE={bundle_rel}")
print(f"CURRENT_RUNNER={state.get('current_runner', '')}")
print(f"NEXT_ACTION={state.get('next_allowed_action', '')}")
print(f"READ_FIRST={bundle_rel}")
PY
