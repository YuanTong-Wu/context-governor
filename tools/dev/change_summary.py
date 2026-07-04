#!/usr/bin/env python3
"""Write a compact local change-control summary."""

from __future__ import annotations

from pathlib import Path

from dev_common import DEV_AUDIT_REL, changed_files, read_json, resolve_root, root_arg


def main() -> int:
    parser = root_arg()
    args = parser.parse_args()
    root = resolve_root(args.root)
    audit_dir = root / DEV_AUDIT_REL
    audit_dir.mkdir(parents=True, exist_ok=True)
    files = changed_files(root, args.changed_file)
    summaries = []
    for name in [
        "preflight_change_summary.json",
        "impact_check_summary.json",
        "schema_compat_check_summary.json",
        "path_consistency_check_summary.json",
        "invariant_check_summary.json",
        "regression_check_summary.json",
    ]:
        path = audit_dir / name
        data = read_json(path, {})
        if data:
            summaries.append(data)
    lines = [
        "# Dev Change Summary",
        "",
        f"- Changed files detected: `{len(files)}`",
        f"- Change note: `{args.change_note or 'not provided'}`",
        "",
        "## Check Summaries",
    ]
    if summaries:
        for item in summaries:
            lines.append(
                f"- `{item.get('script', Path(item.get('path', '')).stem or 'unknown')}`: `{item.get('verdict', 'UNKNOWN')}` "
                f"failures=`{item.get('failure_count', 0)}` warnings=`{item.get('warning_count', 0)}`"
            )
    else:
        lines.append("- No check summaries were found.")
    lines.extend(["", "## Files", ""])
    for path in files[:200]:
        lines.append(f"- `{path}`")
    if len(files) > 200:
        lines.append(f"- ... {len(files) - 200} more")
    out = audit_dir / "CHANGE_SUMMARY.md"
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
