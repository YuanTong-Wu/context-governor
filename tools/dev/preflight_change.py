#!/usr/bin/env python3
"""Classify local changes before editing context-control files."""

from __future__ import annotations

from pathlib import Path

from dev_common import changed_files, resolve_root, root_arg, write_risk_outputs


def classify(path: str) -> dict[str, str]:
    lower = path.lower()
    checks = ["run_dev_checks.sh"]
    risk_level = "LOW"
    risk_type = "ordinary"
    notes = "No special context-control surface detected."

    if path in {"BOOT.md", "START_HERE_MEMORY.md", "AGENTS.md"} or "boot" in Path(path).name.lower():
        risk_level = "CRITICAL"
        risk_type = "startup_entry"
        checks = [
            "startup_budget_test.py",
            "recursive_entry_detector.py",
            "context_integrity_check.py",
            "tools/context/run_context_governor_all.sh",
        ]
        notes = "Startup entry changes can expand context load or create recursive entry points."
    elif path.startswith("context/SYSTEM_INVARIANTS") or path.startswith("context/AUTHORITY") or "invariant" in lower:
        risk_level = "CRITICAL"
        risk_type = "invariant_or_authority"
        checks = ["context_integrity_check.py", "startup_budget_test.py", "schema_compat_check.py"]
        notes = "Invariant changes can alter non-negotiable constraints."
    elif path.startswith("context/schemas") or path.endswith(".jsonschema") or "schema" in lower:
        risk_level = "HIGH"
        risk_type = "schema"
        checks = ["schema_compat_check.py", "regression_check.py", "tools/context/run_context_governor_all.sh"]
        notes = "Schema changes require compatibility checks."
    elif path == "context/global/PROJECT_REGISTRY.json":
        risk_level = "HIGH"
        risk_type = "project_registry"
        checks = [
            "path_consistency_check.py",
            "schema_compat_check.py",
            "test_project_registry.py",
            "test_active_project_switch.py",
            "tools/context/run_context_governor_all.sh",
        ]
        notes = "Project registry changes can break active project routing and project isolation."
    elif path.startswith("context/global") or path.startswith("context/projects"):
        risk_level = "HIGH"
        risk_type = "project_registry"
        checks = ["path_consistency_check.py", "schema_compat_check.py", "test_project_registry.py", "test_active_project_switch.py"]
        notes = "Project registry changes can break active project routing."
    elif path.startswith("context/indexes"):
        risk_level = "HIGH"
        risk_type = "index_surface"
        checks = ["build_index_views.py", "test_index_views.py", "test_query_index.py"]
        notes = "Index changes must remain query-only at startup."
    elif path.startswith("tools/context"):
        risk_level = "HIGH"
        risk_type = "context_tooling"
        checks = ["recursive_entry_detector.py", "tools/context/run_context_governor_all.sh", "tools/context/tests/test_*.py"]
        notes = "Context tooling changes require the governor suite."
    elif path.startswith("tools/dev"):
        risk_level = "MEDIUM"
        risk_type = "dev_change_control"
        checks = ["tools/dev/run_dev_checks.sh"]
        notes = "Change-control tooling should self-check."
    elif path.startswith("docs/context") or path.startswith("docs/dev"):
        risk_level = "MEDIUM"
        risk_type = "operating_docs"
        checks = ["recursive_entry_detector.py"]
        notes = "Docs must not become alternate startup entry files."

    return {
        "path": path,
        "risk_level": risk_level,
        "risk_type": risk_type,
        "required_checks": ";".join(checks),
        "notes": notes,
    }


def main() -> int:
    parser = root_arg()
    args = parser.parse_args()
    root = resolve_root(args.root)
    rows = [classify(path) for path in changed_files(root, args.changed_file)]
    if not rows:
        rows = [
            {
                "path": "",
                "risk_level": "UNKNOWN",
                "risk_type": "UNKNOWN_CHANGE_SURFACE",
                "required_checks": "git status --short;--changed-file;manual_change_surface_review",
                "notes": "No git or explicit changed files were detected; the changed surface must be supplied or reviewed manually.",
            }
        ]
    summary = write_risk_outputs(root, "preflight_change", rows)
    print(summary["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
