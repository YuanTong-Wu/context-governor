#!/usr/bin/env python3
"""Verify startup budget pass on the real root and failure on an unsafe fixture."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path

from test_common import assert_true, read_json, run_cmd


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["path"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def unsafe_fixture(repo: Path, tmp_root: Path) -> None:
    write(tmp_root / "BOOT.md", "# BOOT\n")
    write(
        tmp_root / "context/TASK_STATE.json",
        '{"project_id":"default","current_runner":"tools/context/run_context_governor_all.sh","holdout_status":"LOCKED","next_allowed_action":"Next"}\n',
    )
    write(tmp_root / "context/CURRENT_VERDICT.json", '{"verdict":"FIXTURE"}\n')
    write(tmp_root / "context/SYSTEM_INVARIANTS.json", '{"boot_limits":{"max_lines":80,"max_chars":4000},"holdout_status_required":"LOCKED"}\n')
    run_cmd(
        [
            "python3",
            str(repo / "tools/context/project/init_project_context.py"),
            "--root",
            str(tmp_root),
            "--project-id",
            "default",
            "--project-root",
            str(tmp_root),
            "--project-name",
            "Fixture",
            "--activate",
        ],
        repo,
    )
    for name in ["FILE_INDEX", "RUNNER_INDEX", "GAP_INDEX", "CASE_INDEX", "EVIDENCE_INDEX"]:
        write_csv(tmp_root / f"context/indexes/views/{name}_VIEW.csv", [{"path": "x", "project_id": "default"}])
    write_csv(
        tmp_root / "context/generated/startup_bundles/default_STARTUP_BUNDLE_MANIFEST.csv",
        [{"role": "bad", "path": "context/indexes/FILE_INDEX.csv", "chars": "10", "lines": "1"}],
    )
    write(
        tmp_root / "context/generated/startup_bundles/default_STARTUP_BUNDLE.md",
        "# Unsafe\ncontext/indexes/FILE_INDEX.csv\nraw evidence content\nNext action: bad\nCurrent runner: `tools/context/run_context_governor_all.sh`\ncontext/indexes/views/FILE_INDEX_VIEW.csv\ncontext/indexes/views/RUNNER_INDEX_VIEW.csv\ncontext/indexes/views/GAP_INDEX_VIEW.csv\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    proc = run_cmd(["python3", "tools/context/startup_budget_test.py", "--root", str(root)], root, expect=None)
    assert_true(proc.returncode in {0, 2}, "startup budget script returned unexpected status")
    real = read_json(root / "var/context_governor_2026_06_24/audit/startup_budget_verdict.json")
    assert_true(real.get("verdict") in {"STARTUP_BUDGET_PASS", "STARTUP_BUDGET_PASS_WITH_WARNINGS"}, f"real startup budget failed: {real}")

    with tempfile.TemporaryDirectory(prefix="context-governor-budget-") as tmp:
        tmp_root = Path(tmp)
        unsafe_fixture(root, tmp_root)
        bad = run_cmd(["python3", str(root / "tools/context/startup_budget_test.py"), "--root", str(tmp_root)], root, expect=None)
        assert_true(bad.returncode != 0, "unsafe startup fixture should fail")
        verdict = read_json(tmp_root / "var/context_governor_2026_06_24/audit/startup_budget_verdict.json")
        assert_true(str(verdict.get("verdict", "")).startswith("STARTUP_BUDGET_FAIL"), "unsafe fixture did not write failing verdict")
    print("startup budget test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

