#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
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
    *)
      echo "[context-control] unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

ROOT="$(cd "$ROOT" && pwd)"
PROJECT_ID="${PROJECT_ID:-default}"
PYTHON="${PYTHON:-python3}"

cd "$ROOT" || exit 1

run() {
  echo "[context-control] $*"
  "$@"
}

run "$PYTHON" tools/context/build_file_index.py --root "$ROOT" --project-id "$PROJECT_ID" || exit 1
run "$PYTHON" tools/context/build_runner_index.py --root "$ROOT" --project-id "$PROJECT_ID" || exit 1
run "$PYTHON" tools/context/build_case_index.py --root "$ROOT" --project-id "$PROJECT_ID" || exit 1
run "$PYTHON" tools/context/build_evidence_index.py --root "$ROOT" --project-id "$PROJECT_ID" || exit 1
run "$PYTHON" tools/context/build_gap_index.py --root "$ROOT" --project-id "$PROJECT_ID" || exit 1
run "$PYTHON" tools/context/build_index_views.py --root "$ROOT" --project-id "$PROJECT_ID" || exit 1

if [ "$PROJECT_ID" = "default" ]; then
  run "$PYTHON" tools/context/build_boot_context.py --root "$ROOT" || exit 1
fi

echo "[context-control] first integrity check"
"$PYTHON" tools/context/context_integrity_check.py --root "$ROOT"
first_check=$?

if [ "$first_check" -ne 0 ]; then
  run "$PYTHON" tools/context/context_repair.py --root "$ROOT" || true
fi

echo "[context-control] second integrity check"
"$PYTHON" tools/context/context_integrity_check.py --root "$ROOT"
second_check=$?
if [ "$second_check" -ne 0 ]; then
  echo "[context-control] integrity still failing after repair"
fi

run "$PYTHON" tools/context/update_task_state.py --root "$ROOT" || exit 1
run "$PYTHON" tools/context/build_index_views.py --root "$ROOT" --project-id "$PROJECT_ID" || exit 1

if [ "$PROJECT_ID" = "default" ]; then
  run "$PYTHON" tools/context/build_boot_context.py --root "$ROOT" || exit 1
fi

echo "[context-control] final integrity check"
"$PYTHON" tools/context/context_integrity_check.py --root "$ROOT"
final_check=$?

"$PYTHON" tools/context/write_final_report.py --root "$ROOT"
report_status=$?

echo "[context-control] summary: var/context_control_2026_06_23/summary.json"
echo "[context-control] verdict: var/context_control_2026_06_23/verdict.json"
echo "[context-control] report: var/context_control_2026_06_23/reports/CONTEXT_MICROKERNEL_REPORT_2026_06_23.md"

if [ "$final_check" -ne 0 ]; then
  exit "$final_check"
fi
exit "$report_status"
