#!/usr/bin/env bash
set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT_ID=""
ALLOW_GOVERNOR_RUNNER=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --allow-governor-runner)
      ALLOW_GOVERNOR_RUNNER=1
      shift
      ;;
    --project-id|--project)
      PROJECT_ID="$2"
      shift 2
      ;;
    *)
      if [ -z "$PROJECT_ID" ]; then
        PROJECT_ID="$1"
        shift
      else
        echo "[continue-project] unknown argument: $1" >&2
        exit 2
      fi
      ;;
  esac
done

ROOT="$(cd "$ROOT" && pwd)"
PROJECT_ID="${PROJECT_ID:-default}"
PYTHON="${PYTHON:-python3}"

cd "$ROOT" || exit 1

write_gap() {
  local gap_type="$1"
  local artifact_path="$2"
  local observed="$3"
  local expected="$4"
  local next_action="$5"
  "$PYTHON" - "$ROOT" "$PROJECT_ID" "$gap_type" "$artifact_path" "$observed" "$expected" "$next_action" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "tools/context"))
from governor_common import append_governor_gap

project_id, gap_type, artifact_path, observed, expected, next_action = sys.argv[2:8]
append_governor_gap(
    root,
    {
        "phase": "continue_project",
        "project_id": project_id,
        "artifact_path": artifact_path,
        "gap_type": gap_type,
        "severity": "HIGH",
        "blocking_level": "BLOCKING",
        "observed_status": observed,
        "expected_status": expected,
        "next_action": next_action,
    },
)
PY
}

bash tools/context/start_project.sh --root "$ROOT" --project-id "$PROJECT_ID"

runner_info="$("$PYTHON" - "$ROOT" "$PROJECT_ID" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
project_id = sys.argv[2]
sys.path.insert(0, str(root / "tools/context"))
from governor_common import get_project, project_abs_path, resolve_runner_path

project = get_project(root, project_id)
state_path = project_abs_path(root, project, project["state_path"])
state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
runner = str(state.get("current_runner", ""))
if runner:
    path = resolve_runner_path(root, project, runner)
else:
    path = Path("")
print(runner)
print(path)
PY
)"
CURRENT_RUNNER="$(printf "%s\n" "$runner_info" | sed -n '1p')"
CURRENT_RUNNER_ABS="$(printf "%s\n" "$runner_info" | sed -n '2p')"

# Refuse a governance runner first: it lives in the workspace, so for a project
# rooted elsewhere it would otherwise be reported as a missing file.
case "$CURRENT_RUNNER" in
  tools/context/run_context_governor_all.sh|tools/context/run_context_control_all.sh|tools/context/start_project.sh|tools/context/continue_project.sh)
    if [ "$ALLOW_GOVERNOR_RUNNER" -ne 1 ]; then
      echo "recursive governor runner blocked: $CURRENT_RUNNER"
      echo "set a business runner first: python3 tools/context/project/set_project_runner.py --root . --project-id $PROJECT_ID tools/<runner>.sh"
      write_gap "recursive_governor_runner_blocked" "$CURRENT_RUNNER" "recursive_control_runner" "non-recursive project runner" "set a business runner with tools/context/project/set_project_runner.py, or pass --allow-governor-runner for an explicit audit run"
      exit 3
    fi
    ;;
esac

if [ -z "$CURRENT_RUNNER" ] || [ ! -f "$CURRENT_RUNNER_ABS" ]; then
  echo "current runner missing: ${CURRENT_RUNNER:-<empty>}"
  "$PYTHON" tools/context/query_index.py --root "$ROOT" --index runner --project-id "$PROJECT_ID" --limit 20 || true
  write_gap "current_runner_missing" "${CURRENT_RUNNER:-<empty>}" "missing" "runner exists" "choose a valid runner from RUNNER_INDEX_VIEW.csv"
  exit 2
fi

case "$CURRENT_RUNNER_ABS" in
  *.py)
    "$PYTHON" "$CURRENT_RUNNER_ABS" --root "$ROOT"
    rc=$?
    ;;
  *.sh)
    bash "$CURRENT_RUNNER_ABS" --root "$ROOT"
    rc=$?
    ;;
  *)
    echo "unsupported runner type: $CURRENT_RUNNER"
    write_gap "unsupported_runner_type" "$CURRENT_RUNNER" "unsupported_suffix" ".py or .sh runner" "set current_runner to a Python or shell runner"
    exit 4
    ;;
esac

if [ "$rc" -ne 0 ]; then
  write_gap "current_runner_failed" "$CURRENT_RUNNER" "exit_code=$rc" "exit_code=0" "inspect the runner output and repair before continuing"
  exit "$rc"
fi

"$PYTHON" tools/context/update_task_state.py --root "$ROOT"
"$PYTHON" tools/context/build_index_views.py --root "$ROOT" --project-id "$PROJECT_ID"
"$PYTHON" tools/context/build_startup_bundle.py --root "$ROOT" --project-id "$PROJECT_ID"
"$PYTHON" tools/context/startup_budget_test.py --root "$ROOT" --project-id "$PROJECT_ID"

"$PYTHON" - "$ROOT" "$PROJECT_ID" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
project_id = sys.argv[2]
sys.path.insert(0, str(root / "tools/context"))
from governor_common import get_project, project_control_path

project = get_project(root, project_id)
bundle = project_control_path(root, project, project["startup_bundle_path"])
try:
    bundle_rel = bundle.relative_to(root)
except ValueError:
    bundle_rel = bundle
print("RUNNER_EXIT_CODE=0")
print(f"LATEST_STARTUP_BUNDLE={bundle_rel}")
PY
