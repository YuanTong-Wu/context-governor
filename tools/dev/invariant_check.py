#!/usr/bin/env python3
"""Check non-negotiable context invariants after local changes."""

from __future__ import annotations

from dev_common import add_check, read_json, resolve_root, root_arg, write_check_outputs


def main() -> int:
    parser = root_arg()
    args = parser.parse_args()
    root = resolve_root(args.root)
    checks: list[dict[str, str]] = []
    invariants = read_json(root / "context/SYSTEM_INVARIANTS.json", {})
    state = read_json(root / "context/TASK_STATE.json", {})
    budget = read_json(root / "context/budgets/GLOBAL_CONTEXT_BUDGET.json", {})

    boot_limits = invariants.get("boot_limits", {}) if isinstance(invariants, dict) else {}
    add_check(checks, "boot_max_lines_invariant", "invariant", "PASS" if int(boot_limits.get("max_lines", 999)) <= 80 else "FAIL", "HIGH", "context/SYSTEM_INVARIANTS.json", str(boot_limits.get("max_lines", "")), "<=80")
    add_check(checks, "boot_max_chars_invariant", "invariant", "PASS" if int(boot_limits.get("max_chars", 999999)) <= 4000 else "FAIL", "HIGH", "context/SYSTEM_INVARIANTS.json", str(boot_limits.get("max_chars", "")), "<=4000")
    add_check(checks, "holdout_required_locked", "invariant", "PASS" if invariants.get("holdout_status_required") == "LOCKED" else "FAIL", "HIGH", "context/SYSTEM_INVARIANTS.json", str(invariants.get("holdout_status_required", "")), "LOCKED")
    add_check(checks, "task_holdout_locked", "invariant", "PASS" if state.get("holdout_status") == "LOCKED" else "FAIL", "HIGH", "context/TASK_STATE.json", str(state.get("holdout_status", "")), "LOCKED")

    forbidden = set(state.get("forbidden_actions", [])) if isinstance(state.get("forbidden_actions"), list) else set()
    for action in ["external_side_effects", "external_side_effect_interfaces", "unlock_holdout_samples", "recursive_entry_files", "startup_full_index_reads"]:
        add_check(checks, f"forbidden_{action}", "invariant", "PASS" if action in forbidden else "FAIL", "HIGH", "context/TASK_STATE.json", "present" if action in forbidden else "missing", "present")

    rules = " ".join(str(item) for item in invariants.get("rules", []))
    for phrase in ["Holdout samples must remain locked", "Recursive entry files are forbidden"]:
        add_check(checks, "rule_" + phrase.lower().replace(" ", "_")[:48], "invariant", "PASS" if phrase in rules else "FAIL", "HIGH", "context/SYSTEM_INVARIANTS.json", "present" if phrase in rules else "missing", phrase)

    add_check(checks, "budget_startup_file_cap", "budget", "PASS" if int(budget.get("startup_bundle_max_files", 999)) <= 8 else "FAIL", "HIGH", "context/budgets/GLOBAL_CONTEXT_BUDGET.json", str(budget.get("startup_bundle_max_files", "")), "<=8")
    add_check(checks, "budget_view_row_cap", "budget", "PASS" if int(budget.get("index_view_max_rows", 999999)) <= 200 else "FAIL", "HIGH", "context/budgets/GLOBAL_CONTEXT_BUDGET.json", str(budget.get("index_view_max_rows", "")), "<=200")

    summary = write_check_outputs(root, "invariant_check", checks)
    print(summary["verdict"])
    return 0 if summary["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
