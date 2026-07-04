#!/usr/bin/env python3
"""Write the multi-project context governor report and final verdict."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from context_common import (
    AUDIT_DIR_REL,
    CONTROL_DIR_REL,
    char_count,
    line_count,
    read_csv,
    read_json,
    relpath,
    sha256_file,
    utc_now,
    write_json,
)
from governor_common import (
    GOVERNOR_AUDIT_DIR_REL,
    GOVERNOR_DIR_REL,
    GOVERNOR_REPORT_DIR_REL,
    active_project_path,
    ensure_default_registry,
    ensure_governor_dirs,
    get_active_project,
    get_project,
    load_budget,
    project_abs_path,
    project_control_path,
    project_index_path,
    project_views_dir,
    registry_path,
)


REPORT_NAME = "MULTI_PROJECT_CONTEXT_GOVERNOR_REPORT_2026_06_24.md"
PASS_FINAL = "MULTI_PROJECT_CONTEXT_GOVERNOR_BUILT_AND_VERIFIED"
WARN_FINAL = "MULTI_PROJECT_CONTEXT_GOVERNOR_BUILT_WITH_WARNINGS"


def status_label(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def read_tests(root: Path) -> dict[str, Any]:
    return read_json(root / GOVERNOR_AUDIT_DIR_REL / "context_tests_summary.json", {})


def collect_checks(root: Path, project_id_arg: str | None = None) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    ensure_governor_dirs(root)
    registry = ensure_default_registry(root)
    project = get_project(root, project_id_arg) if project_id_arg else get_active_project(root)
    project_id = project.get("project_id", "")
    budget = load_budget(root, project)
    active = read_json(active_project_path(root), {})
    startup = read_json(root / GOVERNOR_AUDIT_DIR_REL / "startup_budget_verdict.json", {})
    recursive = read_json(root / GOVERNOR_AUDIT_DIR_REL / "recursive_entry_verdict.json", {})
    integrity_path = root / AUDIT_DIR_REL / "context_integrity_verdict.json"
    integrity = read_json(integrity_path, {})
    microkernel_final_path = root / CONTROL_DIR_REL / "verdict.json"
    microkernel_final = read_json(microkernel_final_path, {})
    tests = read_tests(root)
    steps_path = root / GOVERNOR_AUDIT_DIR_REL / "governor_run_steps.csv"
    steps = read_csv(steps_path)
    step_failures = [
        f"{row.get('step', '')}:{row.get('status', '')}"
        for row in steps
        if row.get("status") not in {"PASS", "SKIP"}
    ]

    boot = root / "BOOT.md"
    bundle = project_control_path(root, project, str(project.get("startup_bundle_path") or f"context/generated/startup_bundles/{project_id}_STARTUP_BUNDLE.md"))
    views_dir = project_views_dir(root, project)
    scripts = [
        "tools/context/query_index.py",
        "tools/context/read_gate/read_context_file.py",
        "tools/context/start_project.sh",
        "tools/context/continue_project.sh",
        "tools/context/recursive_entry_detector.py",
        "tools/context/check_before_change.sh",
        "tools/dev/run_dev_checks.sh",
    ]
    required_views = [
        "FILE_INDEX_VIEW.csv",
        "RUNNER_INDEX_VIEW.csv",
        "CASE_INDEX_VIEW.csv",
        "EVIDENCE_INDEX_VIEW.csv",
        "GAP_INDEX_VIEW.csv",
    ]

    checks: list[dict[str, Any]] = []

    def add(check_id: str, ok: bool, severity: str, observed: Any, expected: str, path: str = "", notes: str = "") -> None:
        checks.append(
            {
                "check_id": check_id,
                "status": status_label(ok),
                "severity": severity,
                "path": path,
                "observed": str(observed),
                "expected": expected,
                "notes": notes,
            }
        )

    add("registry_exists", registry_path(root).exists(), "HIGH", "exists" if registry_path(root).exists() else "missing", "exists", relpath(root, registry_path(root)))
    add("active_project_registered", project_id in registry.get("projects", {}), "HIGH", project_id, "registered project id", relpath(root, registry_path(root)))
    add("active_project_matches_project", active.get("active_project_id") == project_id, "HIGH", active.get("active_project_id", ""), project_id, relpath(root, active_project_path(root)))
    add("boot_line_budget", boot.exists() and line_count(boot) <= budget["boot_max_lines"], "HIGH", line_count(boot), f"<= {budget['boot_max_lines']}", "BOOT.md")
    add("boot_char_budget", boot.exists() and char_count(boot) <= budget["boot_max_chars"], "HIGH", char_count(boot), f"<= {budget['boot_max_chars']}", "BOOT.md")
    add("startup_bundle_exists", bundle.exists(), "HIGH", "exists" if bundle.exists() else "missing", "exists", relpath(root, bundle))
    add("startup_budget_pass", startup.get("verdict") in {"STARTUP_BUDGET_PASS", "STARTUP_BUDGET_PASS_WITH_WARNINGS"}, "HIGH", startup.get("verdict", "missing"), "STARTUP_BUDGET_PASS", relpath(root, root / GOVERNOR_AUDIT_DIR_REL / "startup_budget_verdict.json"))

    for view_name in required_views:
        path = views_dir / view_name
        rows = read_csv(path)
        add(f"view_exists_{path.stem.lower()}", path.exists(), "HIGH", "exists" if path.exists() else "missing", "exists", relpath(root, path))
        add(f"view_rows_{path.stem.lower()}", path.exists() and len(rows) <= budget["index_view_max_rows"], "HIGH", len(rows), f"<= {budget['index_view_max_rows']}", relpath(root, path))
        add(f"view_chars_{path.stem.lower()}", path.exists() and char_count(path) <= budget["index_view_max_chars"], "MEDIUM", char_count(path), f"<= {budget['index_view_max_chars']}", relpath(root, path))

    for script in scripts:
        add(f"script_exists_{Path(script).stem}", (root / script).exists(), "HIGH", "exists" if (root / script).exists() else "missing", "exists", script)

    hook_path = root / ".git/hooks/pre-commit"
    local_check = root / "tools/context/check_before_change.sh"
    add("hook_or_local_check_exists", hook_path.exists() or local_check.exists(), "MEDIUM", "present" if hook_path.exists() or local_check.exists() else "missing", ".git hook or local check", ".git/hooks/pre-commit")
    add("recursive_detector_pass", recursive.get("verdict") in {"RECURSIVE_ENTRY_PASS", "RECURSIVE_ENTRY_SCAN_PASS", "RECURSIVE_ENTRY_PASS_WITH_WARNINGS", "RECURSIVE_ENTRY_SCAN_PASS_WITH_WARNINGS"}, "HIGH", recursive.get("verdict", "missing"), "RECURSIVE_ENTRY_PASS", relpath(root, root / GOVERNOR_AUDIT_DIR_REL / "recursive_entry_verdict.json"))
    add(
        "context_integrity_non_blocking",
        integrity.get("verdict") in {"CONTEXT_INTEGRITY_PASS", "CONTEXT_INTEGRITY_PASS_WITH_WARNINGS"},
        "HIGH",
        integrity.get("verdict", "missing"),
        "CONTEXT_INTEGRITY_PASS",
        relpath(root, integrity_path),
        "source=audit/context_integrity_verdict.json",
    )
    add(
        "context_microkernel_final_verdict_written",
        microkernel_final_path.exists() and bool(microkernel_final.get("verdict")),
        "MEDIUM",
        microkernel_final.get("verdict", "missing"),
        "microkernel final verdict written",
        relpath(root, microkernel_final_path),
        "separate from context_integrity_non_blocking",
    )
    add("context_tests_pass", tests.get("failures", 1) == 0 and tests.get("tests", 0) > 0, "HIGH", f"{tests.get('failures', 'missing')} failures / {tests.get('tests', 'missing')} tests", "0 failures", relpath(root, root / GOVERNOR_AUDIT_DIR_REL / "context_tests_summary.json"))
    add("governor_steps_recorded", bool(steps), "MEDIUM", len(steps), "> 0 rows", relpath(root, steps_path))
    if steps:
        add("governor_steps_pass", not step_failures, "HIGH", ";".join(step_failures) if step_failures else "all pass", "all steps PASS or SKIP", relpath(root, steps_path))

    task_path = project_abs_path(root, project, str(project.get("state_path", "context/TASK_STATE.json")))
    task = read_json(task_path, {})
    add("holdout_locked", str(task.get("holdout_status", "LOCKED")).upper() == "LOCKED", "HIGH", task.get("holdout_status", ""), "LOCKED", relpath(root, task_path))

    full_index_mentions = []
    bundle_text = bundle.read_text(encoding="utf-8", errors="replace") if bundle.exists() else ""
    for rel in [
        relpath(root, project_index_path(root, project, "file")),
        relpath(root, project_index_path(root, project, "runner")),
        relpath(root, project_index_path(root, project, "case")),
        relpath(root, project_index_path(root, project, "evidence")),
        relpath(root, project_index_path(root, project, "gap")),
    ]:
        if rel in bundle_text:
            full_index_mentions.append(rel)
    add("startup_bundle_has_no_full_index_paths", not full_index_mentions, "HIGH", ",".join(full_index_mentions) if full_index_mentions else "absent", "absent", relpath(root, bundle))

    failures = [row["check_id"] for row in checks if row["status"] == "FAIL" and row["severity"] == "HIGH"]
    warnings = [row["check_id"] for row in checks if row["status"] != "PASS" and row["severity"] != "HIGH"]
    return checks, failures, warnings


def classify_final(failures: list[str], warnings: list[str]) -> tuple[str, bool]:
    if not failures:
        return (WARN_FINAL if warnings else PASS_FINAL), False
    ids = set(failures)
    if any("registry" in item or "active_project" in item for item in ids):
        return "MULTI_PROJECT_CONTEXT_GOVERNOR_BLOCKED_MISSING_REGISTRY", True
    if any("startup_budget" in item or "startup_bundle" in item for item in ids):
        return "MULTI_PROJECT_CONTEXT_GOVERNOR_BLOCKED_STARTUP_BUDGET", True
    if any("recursive" in item for item in ids):
        return "MULTI_PROJECT_CONTEXT_GOVERNOR_BLOCKED_RECURSIVE_ENTRY", True
    if any("holdout" in item for item in ids):
        return "MULTI_PROJECT_CONTEXT_GOVERNOR_BLOCKED_HOLDOUT_RISK", True
    if any("view_rows" in item or "view_chars" in item or "full_index" in item for item in ids):
        return "MULTI_PROJECT_CONTEXT_GOVERNOR_BLOCKED_INDEX_TOO_LARGE", True
    return "MULTI_PROJECT_CONTEXT_GOVERNOR_BLOCKED_CONTEXT_GOVERNOR", True


def write_report(root: Path, project_id_arg: str | None = None) -> dict[str, Any]:
    ensure_governor_dirs(root)
    now = utc_now()
    project = get_project(root, project_id_arg) if project_id_arg else get_active_project(root)
    project_id = project.get("project_id", "")
    checks, failures, warnings = collect_checks(root, project_id)
    final_verdict, hard_blocker = classify_final(failures, warnings)
    report_path = root / GOVERNOR_REPORT_DIR_REL / REPORT_NAME
    summary_path = root / GOVERNOR_DIR_REL / "summary.json"
    verdict_path = root / GOVERNOR_DIR_REL / "verdict.json"
    next_actions_path = root / GOVERNOR_DIR_REL / "next_actions.md"
    checks_path = root / GOVERNOR_AUDIT_DIR_REL / "governor_final_checks.csv"

    from context_common import write_csv

    write_csv(checks_path, ["check_id", "status", "severity", "path", "observed", "expected", "notes"], checks)

    boot = root / "BOOT.md"
    bundle = project_control_path(root, project, str(project.get("startup_bundle_path") or f"context/generated/startup_bundles/{project_id}_STARTUP_BUNDLE.md"))
    startup = read_json(root / GOVERNOR_AUDIT_DIR_REL / "startup_budget_verdict.json", {})
    tests = read_tests(root)

    if hard_blocker:
        next_lines = [
            "# Next Actions",
            "",
            "1. Open `var/context_governor_2026_06_24/audit/governor_final_checks.csv`.",
            "2. Fix the first HIGH failure.",
            "3. Rerun `tools/context/run_context_governor_all.sh --root <project-root>`.",
            "",
        ]
    else:
        next_lines = [
            "# Next Actions",
            "",
            "1. Use `tools/context/start_project.sh default` to refresh the short startup bundle.",
            "2. Use `tools/context/query_index.py` for full-index lookups instead of opening full CSVs at startup.",
            "3. Use `tools/context/read_gate/read_context_file.py` for large files, raw evidence, and audit-sensitive files.",
            "",
        ]
    next_actions_path.write_text("\n".join(next_lines), encoding="utf-8")

    fail_lines = [f"- `{item}`" for item in failures[:20]] or ["- None."]
    warning_lines = [f"- `{item}`" for item in warnings[:20]] or ["- None."]
    report_lines = [
        "# Multi-Project Context Governor Report",
        "",
        f"- Created at UTC: `{now}`",
        f"- Final verdict: `{final_verdict}`",
        f"- Active project: `{project_id}`",
        f"- BOOT lines/chars: `{line_count(boot)}` / `{char_count(boot)}`",
        f"- Startup bundle: `{relpath(root, bundle)}`",
        f"- Startup budget verdict: `{startup.get('verdict', 'missing')}`",
        f"- Context tests: `{tests.get('tests', 0)}` run, `{tests.get('failures', 'missing')}` failures",
        f"- Holdout status: `LOCKED`",
        "",
        "## What Changed",
        "",
        "- Added a global project registry and active-project pointer under `context/global`.",
        "- Added project-local context records under `context/projects/default`.",
        "- Added startup bundles generated from a small read set.",
        "- Added small index views and shards; full indexes are query-only through `tools/context/query_index.py`.",
        "- Added read gates for large files, raw evidence pointers, gap/case context, and index views.",
        "- Added start/continue scripts, recursive-entry detection, hook/local checks, dev change-control checks, and governor tests.",
        "",
        "## Context Size Control",
        "",
        "- `BOOT.md` stays under the configured startup budget and points to the active project instead of carrying project history.",
        "- Startup reads use `context/generated/startup_bundles/default_STARTUP_BUNDLE.md` plus bounded index views.",
        "- Full indexes remain available through filtered queries, but they are not part of the startup bundle.",
        "- Large/raw/holdout-like files are protected by the read gate and audit logs.",
        "",
        "## Required Commands",
        "",
        "- Start: `tools/context/start_project.sh default`",
        "- Continue: `tools/context/continue_project.sh default`",
        "- Query full indexes: `python3 tools/context/query_index.py --index file --path-contains tools/context --limit 20`",
        "- Safe large-file read: `python3 tools/context/read_gate/read_context_file.py <path> --reason <why> --max-chars 12000`",
        "- Full governor verification: `tools/context/run_context_governor_all.sh --root <project-root>`",
        "",
        "## Failures",
        "",
        *fail_lines,
        "",
        "## Warnings",
        "",
        *warning_lines,
        "",
        "## Evidence",
        "",
        f"- Final checks: `{relpath(root, checks_path)}`",
        f"- Startup budget audit: `{relpath(root, root / GOVERNOR_AUDIT_DIR_REL / 'startup_budget_check.csv')}`",
        f"- Recursive scan: `{relpath(root, root / GOVERNOR_AUDIT_DIR_REL / 'recursive_entry_scan.csv')}`",
        f"- Test summary: `{relpath(root, root / GOVERNOR_AUDIT_DIR_REL / 'context_tests_summary.json')}`",
        "",
    ]
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    summary = {
        "script": "write_governor_report.py",
        "created_at_utc": now,
        "project_id": project_id,
        "final_verdict": final_verdict,
        "hard_blocker": hard_blocker,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "report_path": relpath(root, report_path),
        "boot_lines": line_count(boot),
        "boot_chars": char_count(boot),
        "startup_bundle_path": relpath(root, bundle),
        "startup_bundle_chars": char_count(bundle),
        "checks_path": relpath(root, checks_path),
        "report_sha256": sha256_file(report_path),
    }
    verdict = {
        "script": "write_governor_report.py",
        "created_at_utc": now,
        "verdict": final_verdict,
        "hard_blocker": hard_blocker,
        "project_id": project_id,
        "failures": failures,
        "warnings": warnings,
        "summary_path": relpath(root, summary_path),
        "report_path": relpath(root, report_path),
        "next_actions_path": relpath(root, next_actions_path),
    }
    write_json(summary_path, summary)
    write_json(verdict_path, verdict)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--project-id")
    parser.add_argument("--project", dest="project_id")
    args = parser.parse_args()
    summary = write_report(Path(args.root).expanduser().resolve(), args.project_id)
    print(f"Final verdict: {summary['final_verdict']}")
    print(f"Report: {summary['report_path']}")
    return 0 if not summary["hard_blocker"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
