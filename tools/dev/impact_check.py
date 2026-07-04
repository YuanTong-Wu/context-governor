#!/usr/bin/env python3
"""Map changed files to required regression surfaces."""

from __future__ import annotations

from dev_common import changed_files, resolve_root, root_arg, write_risk_outputs


def impact(path: str) -> dict[str, str]:
    surfaces: list[str] = []
    lower = path.lower()
    if path in {"BOOT.md", "context/TASK_STATE.json", "context/CURRENT_VERDICT.json"}:
        surfaces.extend(["startup_budget", "context_integrity", "recursive_entry"])
    if path.startswith("context/global") or path.startswith("context/projects"):
        surfaces.extend(["project_registry", "active_project_switch", "path_consistency"])
    if path.startswith("context/indexes") or "index" in lower:
        surfaces.extend(["index_views", "query_index"])
    if path.startswith("tools/context"):
        surfaces.extend(["context_governor_all", "context_tests"])
    if path.startswith("tools/dev"):
        surfaces.extend(["dev_checks"])
    if path.startswith("context/schemas") or "schema" in lower:
        surfaces.extend(["schema_compat"])
    if "invariant" in lower or path.startswith("context/SYSTEM_INVARIANTS"):
        surfaces.extend(["invariant_check"])
    if "holdout" in lower:
        surfaces.extend(["holdout_lock"])
    if not surfaces:
        surfaces.append("change_summary")
    unique = sorted(set(surfaces))
    level = "HIGH" if any(item in unique for item in ["startup_budget", "context_governor_all", "schema_compat", "invariant_check"]) else "MEDIUM"
    return {
        "path": path,
        "risk_level": level,
        "risk_type": "impact_surface",
        "required_checks": ";".join(unique),
        "notes": "Run all listed checks before treating the change as safe.",
    }


def main() -> int:
    parser = root_arg()
    args = parser.parse_args()
    root = resolve_root(args.root)
    rows = [impact(path) for path in changed_files(root, args.changed_file)]
    if not rows:
        rows = [
            {
                "path": "",
                "risk_level": "LOW",
                "risk_type": "no_detected_changes",
                "required_checks": "change_summary",
                "notes": "No changed files detected.",
            }
        ]
    summary = write_risk_outputs(root, "impact_check", rows)
    print(summary["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
