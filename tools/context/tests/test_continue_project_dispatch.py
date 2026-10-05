#!/usr/bin/env python3
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from test_common import assert_true, run_cmd


STATE_FILES = [
    Path("context/TASK_STATE.json"),
    Path("context/projects/default/TASK_STATE.json"),
    Path("context/global/ACTIVE_PROJECT.json"),
    Path("context/global/PROJECT_REGISTRY.json"),
    Path("context/global/PROJECTS.csv"),
]


def backup_files(root: Path) -> dict[Path, bytes | None]:
    data: dict[Path, bytes | None] = {}
    for rel in STATE_FILES:
        path = root / rel
        data[rel] = path.read_bytes() if path.exists() else None
    return data


def restore_files(root: Path, backups: dict[Path, bytes | None]) -> None:
    for rel, data in backups.items():
        path = root / rel
        if data is None:
            path.unlink(missing_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def write_state(root: Path, runner: str) -> None:
    state = {
        "task_state_version": 1,
        "project_id": "default",
        "current_phase": "p0_dispatch_test",
        "current_runner": runner,
        "current_runner_args": [],
        "holdout_status": "LOCKED",
        "latest_gap_queue_path": "var/context_governor_2026_06_24/gap_queue.csv",
        "latest_verdict_path": "var/context_governor_2026_06_24/verdict.json",
        "next_allowed_action": "run_current_runner_once",
        "updated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    for rel in STATE_FILES[:2]:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_runner_files(root: Path) -> Path:
    runner_dir = root / "tools/context/p0_test_runners"
    runner_dir.mkdir(parents=True, exist_ok=True)
    (runner_dir / "p0_runner.py").write_text(
        """#!/usr/bin/env python3
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--root", default=".")
args = parser.parse_args()
marker = Path(args.root) / "var/context_governor_p0_fix_2026_06_24/test_runners/py_marker.txt"
marker.parent.mkdir(parents=True, exist_ok=True)
marker.write_text("python\\n", encoding="utf-8")
""",
        encoding="utf-8",
    )
    (runner_dir / "p0_runner.sh").write_text(
        """#!/usr/bin/env bash
set -euo pipefail
ROOT="."
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
mkdir -p "$ROOT/var/context_governor_p0_fix_2026_06_24/test_runners"
printf 'shell\\n' > "$ROOT/var/context_governor_p0_fix_2026_06_24/test_runners/sh_marker.txt"
""",
        encoding="utf-8",
    )
    (runner_dir / "p0_runner.txt").write_text("unsupported\n", encoding="utf-8")
    for script in ("p0_runner.py", "p0_runner.sh"):
        (runner_dir / script).chmod(0o755)
    return runner_dir


def assert_gap_contains(root: Path, needle: str) -> None:
    gap_path = root / "var/context_governor_2026_06_24/gap_queue.csv"
    assert_true(gap_path.exists(), "gap queue should exist")
    assert_true(needle in gap_path.read_text(encoding="utf-8"), f"gap queue should contain {needle}")


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    backups = backup_files(root)
    runner_dir = write_runner_files(root)
    marker_dir = root / "var/context_governor_p0_fix_2026_06_24/test_runners"
    try:
        write_state(root, "tools/context/p0_test_runners/p0_runner.py")
        result = run_cmd(
            ["bash", "tools/context/continue_project.sh", "default", "--root", str(root)],
            root,
            timeout=180,
        )
        assert_true("RUNNER_EXIT_CODE=0" in result.stdout, "python runner should complete")
        assert_true((marker_dir / "py_marker.txt").exists(), "python runner marker should exist")

        write_state(root, "tools/context/p0_test_runners/p0_runner.sh")
        result = run_cmd(
            ["bash", "tools/context/continue_project.sh", "default", "--root", str(root)],
            root,
            timeout=180,
        )
        assert_true("RUNNER_EXIT_CODE=0" in result.stdout, "shell runner should complete")
        assert_true((marker_dir / "sh_marker.txt").exists(), "shell runner marker should exist")

        write_state(root, "tools/context/p0_test_runners/missing_runner.py")
        run_cmd(
            ["bash", "tools/context/continue_project.sh", "default", "--root", str(root)],
            root,
            expect=2,
            timeout=180,
        )
        assert_gap_contains(root, "current_runner_missing")

        write_state(root, "tools/context/run_context_governor_all.sh")
        run_cmd(
            ["bash", "tools/context/continue_project.sh", "default", "--root", str(root)],
            root,
            expect=3,
            timeout=180,
        )
        assert_gap_contains(root, "recursive_governor_runner_blocked")

        write_state(root, "tools/context/p0_test_runners/p0_runner.txt")
        run_cmd(
            ["bash", "tools/context/continue_project.sh", "default", "--root", str(root)],
            root,
            expect=4,
            timeout=180,
        )
        assert_gap_contains(root, "unsupported_runner_type")
    finally:
        restore_files(root, backups)
        shutil.rmtree(runner_dir, ignore_errors=True)
        shutil.rmtree(marker_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
