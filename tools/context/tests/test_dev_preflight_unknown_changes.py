#!/usr/bin/env python3
import csv
import tempfile
from pathlib import Path

from test_common import assert_true, read_json, run_cmd


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    repo = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory(prefix="context-preflight-empty-") as tmp:
        empty_root = Path(tmp)
        result = run_cmd(["python3", str(repo / "tools/dev/preflight_change.py"), "--root", str(empty_root)], repo, timeout=120)
        assert_true("UNKNOWN_CHANGE_SURFACE" in result.stdout, "empty non-git root should be unknown, not low risk")
        summary = read_json(empty_root / "var/dev_change_control_2026_06_24/preflight_change_summary.json")
        assert_true(summary.get("unknown_change_surface_count") == 1, "unknown count should be recorded")
        assert_true(summary.get("verdict") == "UNKNOWN_CHANGE_SURFACE", "unknown change surface should be verdict")

    run_cmd(
        [
            "python3",
            "tools/dev/preflight_change.py",
            "--root",
            str(repo),
            "--changed-file",
            "BOOT.md",
            "--changed-file",
            "context/global/PROJECT_REGISTRY.json",
            "--changed-file",
            "tools/context/continue_project.sh",
        ],
        repo,
        timeout=120,
    )
    rows = read_rows(repo / "var/dev_change_control_2026_06_24/preflight_change.csv")
    by_path = {row["path"]: row for row in rows}
    assert_true({"BOOT.md", "context/global/PROJECT_REGISTRY.json", "tools/context/continue_project.sh"} <= set(by_path), "all explicit files should be checked")
    assert_true("startup_budget_test.py" in by_path["BOOT.md"]["required_checks"], "BOOT changes should require startup budget test")
    assert_true("tools/context/run_context_governor_all.sh" in by_path["BOOT.md"]["required_checks"], "BOOT changes should require governor all")
    assert_true("test_project_registry.py" in by_path["context/global/PROJECT_REGISTRY.json"]["required_checks"], "registry changes should require registry test")
    assert_true("tools/context/tests/test_*.py" in by_path["tools/context/continue_project.sh"]["required_checks"], "context tooling changes should require context tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
