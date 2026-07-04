#!/usr/bin/env bash
set -uo pipefail

ROOT="$(pwd)"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --project-id|--project)
      PROJECT_ID="$2"
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
    *)
      echo "[governor] unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

ROOT="$(cd "$ROOT" && pwd)"
PYTHON="${PYTHON:-python3}"
PROJECT_ID="${PROJECT_ID:-default}"
PROJECT_NAME="${PROJECT_NAME:-Default Project}"
PROJECT_ROOT="${PROJECT_ROOT:-$ROOT}"
STEP_TIMEOUT="${CONTEXT_GOVERNOR_STEP_TIMEOUT:-${GOVERNOR_STEP_TIMEOUT:-120}}"

cd "$ROOT" || exit 1
mkdir -p var/context_governor_2026_06_24/audit var/context_governor_2026_06_24/reports

status=0
failures=0
AUDIT="var/context_governor_2026_06_24/audit/governor_run_steps.csv"
printf "step,status,exit_code,start_at_utc,end_at_utc,duration_seconds,timeout_seconds,command\n" > "$AUDIT"

now_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

append_step_csv() {
  "$PYTHON" - "$AUDIT" "$1" "$2" "$3" "$4" "$5" "$6" "$STEP_TIMEOUT" "$7" <<'PY'
import csv
import sys
from pathlib import Path

path = Path(sys.argv[1])
fields = ["step", "status", "exit_code", "start_at_utc", "end_at_utc", "duration_seconds", "timeout_seconds", "command"]
row = dict(zip(fields, sys.argv[2:10]))
with path.open("a", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writerow(row)
PY
}

record_issue() {
  local name="$1"
  local step_status="$2"
  local rc="$3"
  local command_text="$4"
  "$PYTHON" - "$ROOT" "$PROJECT_ID" "$name" "$step_status" "$rc" "$command_text" "$STEP_TIMEOUT" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "tools/context"))
from governor_common import append_governor_blocked, append_governor_gap

project_id, name, step_status, rc, command_text, timeout_seconds = sys.argv[2:8]
gap_type = "governor_step_timeout" if step_status == "TIMEOUT" else "governor_step_failed"
expected = f"step completes within {timeout_seconds}s" if step_status == "TIMEOUT" else "exit_code=0"
append_governor_gap(
    root,
    {
        "phase": "run_context_governor_all",
        "project_id": project_id,
        "artifact_path": name,
        "gap_type": gap_type,
        "severity": "HIGH",
        "blocking_level": "BLOCKING",
        "observed_status": f"{step_status}:{rc}",
        "expected_status": expected,
        "next_action": "inspect governor_run_steps.csv and rerun the failing step after repair",
        "notes": command_text,
    },
)
append_governor_blocked(
    root,
    {
        "phase": "run_context_governor_all",
        "project_id": project_id,
        "artifact_path": name,
        "reason": gap_type,
        "severity": "HIGH",
        "next_action": "repair the failing governor step before accepting the final verdict",
        "notes": command_text,
    },
)
PY
}

run_with_timeout() {
  "$PYTHON" - "$STEP_TIMEOUT" "$@" <<'PY'
import subprocess
import sys

timeout = float(sys.argv[1])
cmd = sys.argv[2:]
try:
    completed = subprocess.run(cmd, timeout=timeout)
except subprocess.TimeoutExpired:
    raise SystemExit(124)
raise SystemExit(completed.returncode)
PY
}

run_step() {
  local name="$1"
  shift
  local start end duration rc step_status command_text
  command_text="$*"
  start="$(now_utc)"
  echo "[governor] $name"
  run_with_timeout "$@"
  rc=$?
  end="$(now_utc)"
  duration="$("$PYTHON" - "$start" "$end" <<'PY'
import datetime as dt
import sys

start = dt.datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00"))
end = dt.datetime.fromisoformat(sys.argv[2].replace("Z", "+00:00"))
print(f"{(end - start).total_seconds():.3f}")
PY
)"
  if [ "$rc" -eq 0 ]; then
    step_status="PASS"
  elif [ "$rc" -eq 124 ]; then
    step_status="TIMEOUT"
  else
    step_status="FAIL"
  fi
  append_step_csv "$name" "$step_status" "$rc" "$start" "$end" "$duration" "$command_text"
  if [ "$step_status" != "PASS" ]; then
    failures=$((failures + 1))
    status=1
    record_issue "$name" "$step_status" "$rc" "$command_text"
  fi
}

run_step init_project "$PYTHON" tools/context/project/init_project_context.py --root "$ROOT" --project-id "$PROJECT_ID" --project-root "$PROJECT_ROOT" --project-name "$PROJECT_NAME" --activate
run_step build_file_index "$PYTHON" tools/context/build_file_index.py --root "$ROOT" --project-id "$PROJECT_ID"
run_step build_runner_index "$PYTHON" tools/context/build_runner_index.py --root "$ROOT" --project-id "$PROJECT_ID"
run_step build_case_index "$PYTHON" tools/context/build_case_index.py --root "$ROOT" --project-id "$PROJECT_ID"
run_step build_evidence_index "$PYTHON" tools/context/build_evidence_index.py --root "$ROOT" --project-id "$PROJECT_ID"
run_step build_gap_index "$PYTHON" tools/context/build_gap_index.py --root "$ROOT" --project-id "$PROJECT_ID"
run_step build_index_views "$PYTHON" tools/context/build_index_views.py --root "$ROOT" --project-id "$PROJECT_ID"
if [ "$PROJECT_ID" = "default" ]; then
  run_step build_boot "$PYTHON" tools/context/build_boot_context.py --root "$ROOT"
fi
run_step integrity_check "$PYTHON" tools/context/context_integrity_check.py --root "$ROOT"
run_step update_task_state "$PYTHON" tools/context/update_task_state.py --root "$ROOT"
run_step rebuild_index_views "$PYTHON" tools/context/build_index_views.py --root "$ROOT" --project-id "$PROJECT_ID"
if [ "$PROJECT_ID" = "default" ]; then
  run_step rebuild_boot "$PYTHON" tools/context/build_boot_context.py --root "$ROOT"
fi
run_step build_startup_bundle "$PYTHON" tools/context/build_startup_bundle.py --root "$ROOT" --project-id "$PROJECT_ID"
run_step startup_budget "$PYTHON" tools/context/startup_budget_test.py --root "$ROOT"
run_step recursive_entry_detector "$PYTHON" tools/context/recursive_entry_detector.py --root "$ROOT"
run_step dev_checks bash tools/dev/run_dev_checks.sh --root "$ROOT"

TEST_AUDIT="var/context_governor_2026_06_24/audit/context_tests.csv"
printf "test,status,exit_code,start_at_utc,end_at_utc,duration_seconds,timeout_seconds\n" > "$TEST_AUDIT"
tests=0
test_failures=0
for test_file in tools/context/tests/test_*.py; do
  [ -e "$test_file" ] || continue
  if [ "$(basename "$test_file")" = "test_common.py" ]; then
    continue
  fi
  tests=$((tests + 1))
  start="$(now_utc)"
  echo "[governor-test] $test_file"
  run_with_timeout "$PYTHON" "$test_file" --root "$ROOT"
  rc=$?
  end="$(now_utc)"
  duration="$("$PYTHON" - "$start" "$end" <<'PY'
import datetime as dt
import sys

start = dt.datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00"))
end = dt.datetime.fromisoformat(sys.argv[2].replace("Z", "+00:00"))
print(f"{(end - start).total_seconds():.3f}")
PY
)"
  if [ "$rc" -eq 0 ]; then
    test_status="PASS"
  elif [ "$rc" -eq 124 ]; then
    test_status="TIMEOUT"
  else
    test_status="FAIL"
  fi
  "$PYTHON" - "$TEST_AUDIT" "$test_file" "$test_status" "$rc" "$start" "$end" "$duration" "$STEP_TIMEOUT" <<'PY'
import csv
import sys
from pathlib import Path

fields = ["test", "status", "exit_code", "start_at_utc", "end_at_utc", "duration_seconds", "timeout_seconds"]
row = dict(zip(fields, sys.argv[2:9]))
with Path(sys.argv[1]).open("a", encoding="utf-8", newline="") as handle:
    csv.DictWriter(handle, fieldnames=fields).writerow(row)
PY
  if [ "$test_status" != "PASS" ]; then
    test_failures=$((test_failures + 1))
    failures=$((failures + 1))
    status=1
    record_issue "context_test:$test_file" "$test_status" "$rc" "$PYTHON $test_file --root $ROOT"
  fi
done

"$PYTHON" - "$ROOT" "$tests" "$test_failures" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(sys.argv[1])
tests = int(sys.argv[2])
failures = int(sys.argv[3])
summary = {
    "tests": tests,
    "failures": failures,
    "verdict": "CONTEXT_GOVERNOR_TESTS_PASS" if failures == 0 and tests > 0 else "CONTEXT_GOVERNOR_TESTS_FAIL",
    "updated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
}
path = root / "var/context_governor_2026_06_24/audit/context_tests_summary.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

run_step final_report "$PYTHON" tools/context/write_governor_report.py --root "$ROOT" --project-id "$PROJECT_ID"

if "$PYTHON" - "$ROOT" "$failures" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
failures = int(sys.argv[2])
path = root / "var/context_governor_2026_06_24/verdict.json"
if not path.exists():
    raise SystemExit(1)
verdict = json.loads(path.read_text(encoding="utf-8"))
raise SystemExit(0 if failures == 0 and not verdict.get("hard_blocker") else 1)
PY
then
  echo "[governor] final verdict is non-blocking"
  exit 0
fi

echo "[governor] final verdict is blocking"
exit 1
