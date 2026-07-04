#!/usr/bin/env python3
"""Write the final context microkernel report and top-level verdict."""

from __future__ import annotations

import argparse
from pathlib import Path

from context_common import (
    AUDIT_DIR_REL,
    CONTROL_DIR_REL,
    REPORT_DIR_REL,
    append_blocked,
    char_count,
    ensure_dirs,
    line_count,
    read_csv,
    read_json,
    relpath,
    sha256_file,
    utc_now,
    write_json,
    write_json_with_self_sha,
)


REPORT_NAME = "CONTEXT_MICROKERNEL_REPORT_2026_06_23.md"


def final_enum(integrity_verdict: str, repair_ran: bool) -> str:
    if integrity_verdict == "CONTEXT_INTEGRITY_PASS":
        return "CONTEXT_MICROKERNEL_REPAIRED_AND_VERIFIED" if repair_ran else "CONTEXT_MICROKERNEL_BUILT_AND_VERIFIED"
    if integrity_verdict == "CONTEXT_INTEGRITY_PASS_WITH_WARNINGS":
        return "CONTEXT_MICROKERNEL_BUILT_WITH_WARNINGS"
    if "RECURSIVE_ENTRY" in integrity_verdict:
        return "CONTEXT_MICROKERNEL_FAIL_RECURSIVE_ENTRY_DETECTED"
    if "BOOT_TOO_LARGE" in integrity_verdict:
        return "CONTEXT_MICROKERNEL_FAIL_BOOT_TOO_LARGE"
    if "HOLDOUT" in integrity_verdict:
        return "CONTEXT_MICROKERNEL_FAIL_HOLDOUT_RISK"
    if "MISSING_POINTER" in integrity_verdict:
        return "CONTEXT_MICROKERNEL_BLOCKED_MISSING_CORE_INPUTS"
    if "SEMANTIC_DRIFT" in integrity_verdict:
        return "CONTEXT_MICROKERNEL_FAIL_SAFETY_BOUNDARY"
    return "CONTEXT_MICROKERNEL_BLOCKED_MISSING_CORE_INPUTS"


def write_report(root: Path) -> dict[str, object]:
    ensure_dirs(root)
    now = utc_now()
    integrity_source = root / AUDIT_DIR_REL / "context_integrity_verdict.json"
    integrity = read_json(integrity_source, {})
    failures = integrity.get("failures", []) if isinstance(integrity, dict) else []
    integrity_verdict = integrity.get("verdict", "") if isinstance(integrity, dict) else ""
    if not integrity_verdict:
        integrity_verdict = "CONTEXT_INTEGRITY_AUDIT_VERDICT_MISSING"
        missing_failure = {
            "check_id": "context_integrity_audit_verdict_exists",
            "path": str(AUDIT_DIR_REL / "context_integrity_verdict.json"),
            "observed": "missing_or_invalid",
            "expected": "context_integrity_check.py writes audit verdict before final report",
            "severity": "HIGH",
        }
        failures = [missing_failure]
        append_blocked(
            root,
            {
                "phase": "write_final_report",
                "artifact_path": str(AUDIT_DIR_REL / "context_integrity_verdict.json"),
                "reason": "missing_context_integrity_audit_verdict",
                "severity": "HIGH",
                "next_action": "Run python3 tools/context/context_integrity_check.py before write_final_report.py.",
                "notes": "Final report must not read var/context_control_2026_06_23/verdict.json as its integrity source.",
            },
        )
    repair_summary = read_json(root / CONTROL_DIR_REL / "audit/context_repair_summary.json", {})
    repair_ran = bool(repair_summary)
    final_verdict = final_enum(integrity_verdict, repair_ran)
    hard_blocker = not final_verdict.endswith("_VERIFIED") and final_verdict != "CONTEXT_MICROKERNEL_BUILT_WITH_WARNINGS"

    report_path = root / REPORT_DIR_REL / REPORT_NAME
    file_rows = read_csv(root / "context/indexes/FILE_INDEX.csv")
    runner_rows = read_csv(root / "context/indexes/RUNNER_INDEX.csv")
    gap_rows = read_csv(root / "context/indexes/GAP_INDEX.csv")

    lines = [
        "# Context Microkernel Report",
        "",
        f"- Created at UTC: `{now}`",
        f"- Final verdict: `{final_verdict}`",
        f"- Integrity verdict: `{integrity_verdict}`",
        f"- Integrity source: `{relpath(root, integrity_source)}`",
        f"- BOOT lines/chars: `{line_count(root / 'BOOT.md')}` / `{char_count(root / 'BOOT.md')}`",
        f"- File index rows: `{len(file_rows)}`",
        f"- Runner index rows: `{len(runner_rows)}`",
        f"- Gap index rows: `{len(gap_rows)}`",
        f"- Holdout status: `LOCKED`",
        "",
        "## Core Outputs",
        "",
        "- `BOOT.md`",
        "- `context/SYSTEM_INVARIANTS.json`",
        "- `context/AUTHORITY_LEVELS.json`",
        "- `context/TASK_STATE.json`",
        "- `context/CURRENT_VERDICT.json`",
        "- `context/indexes/FILE_INDEX.csv`",
        "- `context/indexes/RUNNER_INDEX.csv`",
        "- `context/indexes/CASE_INDEX.csv`",
        "- `context/indexes/EVIDENCE_INDEX.csv`",
        "- `context/indexes/GAP_INDEX.csv`",
        "- `context/generated/BOOT_SOURCE_MANIFEST.csv`",
        "- `context/generated/BOOT_BUILD_MANIFEST.csv`",
        "",
        "## Verification",
        "",
        f"- `tools/context/context_integrity_check.py` writes `{relpath(root, integrity_source)}` and enforces BOOT size, pointer existence, recursion bans, state size, holdout lock, and authority ceilings.",
        "- `tools/context/run_context_control_all.sh` rebuilds indexes, regenerates BOOT, repairs common failures, refreshes task state, and writes this report.",
        "",
    ]
    if failures:
        lines.extend(["## Remaining Blockers", ""])
        for failure in failures[:10]:
            lines.append(f"- `{failure.get('check_id')}` at `{failure.get('path')}`: {failure.get('observed')} -> {failure.get('expected')}")
        lines.append("")
    else:
        lines.extend(["## Remaining Blockers", "", "- None.", ""])

    next_actions_path = root / CONTROL_DIR_REL / "next_actions.md"
    if failures:
        next_text = "\n".join(
            [
                "# Next Actions",
                "",
                "1. Inspect `var/context_control_2026_06_23/audit/context_integrity_check.csv`.",
                "2. Repair the first listed hard blocker.",
                "3. Rerun `tools/context/run_context_control_all.sh`.",
                "",
            ]
        )
    else:
        next_text = "\n".join(
            [
                "# Next Actions",
                "",
                "1. Use `BOOT.md` as the startup entry point.",
                "2. Rerun `tools/context/run_context_control_all.sh` after context edits.",
                "3. Keep detailed project memory in indexed source files, not in BOOT.",
                "",
            ]
        )
    next_actions_path.write_text(next_text, encoding="utf-8")
    report_path.write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "script": "write_final_report.py",
        "created_at_utc": now,
        "final_verdict": final_verdict,
        "integrity_verdict": integrity_verdict,
        "integrity_source_path": relpath(root, integrity_source),
        "hard_blocker": hard_blocker,
        "report_path": str(REPORT_DIR_REL / REPORT_NAME),
        "boot_line_count": line_count(root / "BOOT.md"),
        "boot_char_count": char_count(root / "BOOT.md"),
        "report_sha256": sha256_file(report_path),
    }
    verdict_doc = {
        "script": "write_final_report.py",
        "created_at_utc": now,
        "verdict": final_verdict,
        "hard_blocker": hard_blocker,
        "integrity_verdict": integrity_verdict,
        "integrity_source_path": relpath(root, integrity_source),
        "report_path": str(REPORT_DIR_REL / REPORT_NAME),
        "summary_path": str(CONTROL_DIR_REL / "summary.json"),
    }
    write_json(root / CONTROL_DIR_REL / "summary.json", summary)
    write_json(root / CONTROL_DIR_REL / "verdict.json", verdict_doc)
    write_json_with_self_sha(
        root / "context/CURRENT_VERDICT.json",
        {
            "current_verdict_version": "1.0",
            "updated_at_utc": now,
            "verdict": final_verdict,
            "hard_blocker": hard_blocker,
            "latest_summary_path": str(CONTROL_DIR_REL / "summary.json"),
            "latest_report_path": str(REPORT_DIR_REL / REPORT_NAME),
            "integrity_verdict": integrity_verdict,
            "failure_count": len(failures),
            "notes": "Final context microkernel verdict.",
        },
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    summary = write_report(Path(args.root).expanduser().resolve())
    print(f"Final verdict: {summary['final_verdict']}")
    print(f"Report: {summary['report_path']}")
    return 0 if not summary["hard_blocker"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
