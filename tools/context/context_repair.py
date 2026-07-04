#!/usr/bin/env python3
"""Repair common context microkernel integrity failures."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from context_common import (
    AUDIT_DIR_REL,
    append_gap,
    copy_to_quarantine,
    ensure_dirs,
    line_count,
    read_json,
    relpath,
    utc_now,
    write_csv,
    write_json_with_self_sha,
    write_script_audit,
)
from context_integrity_check import RECURSIVE_ENTRY_NAMES, find_recursive_entry_files, run_checks


QUARANTINE_FIELDS = ["original_path", "quarantine_path", "sha256", "reason", "created_at_utc"]


def run_script(root: Path, script: str) -> int:
    return subprocess.call([sys.executable, str(root / script), "--root", str(root)], cwd=str(root))


def compact_task_state(root: Path) -> None:
    now = utc_now()
    state = {
        "task_state_version": "1.0",
        "updated_at_utc": now,
        "updated_by": "tools/context/context_repair.py",
        "current_phase": "context_microkernel_repair",
        "context_integrity_status": "REPAIR_IN_PROGRESS",
        "current_runner": "tools/context/run_context_control_all.sh",
        "current_runner_args": [],
        "next_allowed_action": "Run tools/context/run_context_control_all.sh.",
        "latest_gap_queue_path": "var/context_control_2026_06_23/gap_queue.csv",
        "latest_manifest_path": "context/generated/BOOT_BUILD_MANIFEST.csv",
        "source_manifest_path": "context/generated/BOOT_SOURCE_MANIFEST.csv",
        "latest_summary_path": "var/context_control_2026_06_23/summary.json",
        "latest_verdict_path": "context/CURRENT_VERDICT.json",
        "writable_output_dir": "var/context_control_2026_06_23",
        "readonly_input_dirs": ["."],
        "holdout_status": "LOCKED",
        "forbidden_actions": [
            "external_side_effects",
            "external_side_effect_interfaces",
            "unlock_holdout_samples",
            "recursive_entry_files",
        ],
        "sha256_self": "",
    }
    write_json_with_self_sha(root / "context/TASK_STATE.json", state)


def compact_current_verdict(root: Path) -> None:
    now = utc_now()
    write_json_with_self_sha(
        root / "context/CURRENT_VERDICT.json",
        {
            "current_verdict_version": "1.0",
            "updated_at_utc": now,
            "verdict": "REPAIR_IN_PROGRESS",
            "hard_blocker": False,
            "latest_summary_path": "var/context_control_2026_06_23/summary.json",
            "latest_report_path": "",
            "notes": "Compacted by context repair.",
        },
    )


def repair(root: Path) -> dict[str, object]:
    ensure_dirs(root)
    repaired: list[str] = []
    quarantine_rows = []

    for path in find_recursive_entry_files(root):
        quarantine_rows.append(copy_to_quarantine(root, path, "recursive entry file forbidden"))
        repaired.append(f"quarantined:{relpath(root, path)}")

    if quarantine_rows:
        write_csv(root / AUDIT_DIR_REL / "recursive_entry_quarantine_manifest.csv", QUARANTINE_FIELDS, quarantine_rows)

    if not (root / "BOOT.md").exists() or line_count(root / "BOOT.md") > 80:
        run_script(root, "tools/context/build_boot_context.py")
        repaired.append("rebuilt_boot")

    if not (root / "context/TASK_STATE.json").exists() or line_count(root / "context/TASK_STATE.json") > 200:
        compact_task_state(root)
        repaired.append("compacted_task_state")

    if not (root / "context/CURRENT_VERDICT.json").exists() or line_count(root / "context/CURRENT_VERDICT.json") > 120:
        compact_current_verdict(root)
        repaired.append("compacted_current_verdict")

    result = run_checks(root)
    if result["verdict"]["hard_blocker"]:
        first = result["verdict"]["failures"][0] if result["verdict"]["failures"] else {}
        append_gap(
            root,
            {
                "phase": "context_control",
                "artifact_path": first.get("path", "."),
                "gap_type": first.get("check_id", "repair_failed"),
                "severity": first.get("severity", "HIGH"),
                "blocking_level": "HARD",
                "observed_status": first.get("observed", "integrity still failing"),
                "expected_status": first.get("expected", "integrity pass"),
                "auto_repairable": "FALSE",
                "repair_attempted": "TRUE",
                "repair_result": "FAILED",
                "next_action": "Inspect context integrity audit and repair the named artifact.",
                "notes": result["verdict"]["verdict"],
            },
        )
    return {"repaired": repaired, "post_repair": result["summary"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    result = repair(root)
    now = utc_now()
    summary = {
        "script": "context_repair.py",
        "created_at_utc": now,
        "repair_count": len(result["repaired"]),
        "repairs": result["repaired"],
        "post_repair_verdict": result["post_repair"].get("verdict"),
    }
    verdict = {
        "script": "context_repair.py",
        "created_at_utc": now,
        "verdict": "CONTEXT_REPAIR_DONE",
        "hard_blocker": result["post_repair"].get("hard_blocker", True),
    }
    write_script_audit(root, "context_repair", summary, verdict, [])
    return 0 if not verdict["hard_blocker"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
