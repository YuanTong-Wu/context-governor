#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check Markdown context budgets for low-context repository maintenance.

This script reads file metadata and optional small configuration only. It is
repository-maintenance infrastructure; it never modifies the files it scans.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "context" / "context_budget.json"
DEFAULT_TOP = 40
SKIP_PARTS = {".git", "__pycache__"}
SKIP_NAMES = {".DS_Store"}

DEFAULT_CONFIG: dict[str, Any] = {
    "budgets_bytes": {
        "startup_entry": 8192,
        "active_index": 10240,
        "domain_index": 15360,
        "archive_index": 15360,
        "handoff": 12288,
        "long_memory": 25600,
        "default_markdown": 25600,
        "startup_pack_total": 40960,
    },
    "startup_files": [
        "AGENTS.md",
        "NORTH_STAR.md",
        "README.md",
        "context/STARTUP_CONTEXT.md",
        "context/INDEX_ACTIVE.md",
        "context/INDEX_DOMAINS.md",
        "START_HERE_MEMORY.md",
    ],
    "archive_prefixes": [
        "var/",
        "outputs/",
        "logs/",
        ".source_cache/",
    ],
}


@dataclass(frozen=True)
class MdFile:
    path: str
    size: int
    role: str
    budget: int
    over_by: int

    @property
    def over_budget(self) -> bool:
        return self.over_by > 0


def load_config() -> dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG_PATH.exists():
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        for key, value in loaded.items():
            if isinstance(value, dict) and isinstance(config.get(key), dict):
                config[key].update(value)
            else:
                config[key] = value
    return config


def relpath(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def should_skip(path: Path) -> bool:
    rel_parts = path.relative_to(ROOT).parts
    return path.name in SKIP_NAMES or any(part in SKIP_PARTS for part in rel_parts)


def iter_markdown_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.md"):
        if should_skip(path) or not path.is_file():
            continue
        files.append(path)
    return sorted(files, key=lambda p: relpath(p).lower())


def starts_with_any(path: str, prefixes: list[str]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def classify(path: str, config: dict[str, Any]) -> str:
    name = path.rsplit("/", 1)[-1]
    upper_name = name.upper()
    archive_prefixes = config.get("archive_prefixes", [])

    if path == "context/INDEX_ACTIVE.md":
        return "active_index"
    if path.startswith("context/INDEX_ARCHIVE"):
        return "archive_index"
    if path.startswith("context/INDEX_"):
        return "domain_index"
    if path in config.get("startup_files", []):
        return "startup_entry"
    if path.startswith("context/") and (upper_name.endswith("HANDOFF.MD") or "HANDOFF" in upper_name):
        return "handoff"
    if starts_with_any(path, archive_prefixes):
        return "archive_payload"
    if path.startswith("memory/") or path.startswith("memory_"):
        return "long_memory"
    if "FULL" in upper_name or "PROMPT" in upper_name or "STATE" in upper_name:
        return "long_memory"
    if "INDEX" in upper_name or name == "project_map.md":
        return "domain_index"
    if "HANDOFF" in upper_name or "CURRENT" in upper_name:
        return "handoff"
    return "default_markdown"


def budget_for(role: str, config: dict[str, Any]) -> int:
    budgets = config["budgets_bytes"]
    if role == "archive_payload":
        return budgets["default_markdown"]
    return budgets.get(role, budgets["default_markdown"])


def collect(config: dict[str, Any]) -> list[MdFile]:
    rows: list[MdFile] = []
    for path in iter_markdown_files():
        rel = relpath(path)
        role = classify(rel, config)
        size = path.stat().st_size
        budget = budget_for(role, config)
        rows.append(MdFile(rel, size, role, budget, max(0, size - budget)))
    return rows


def format_bytes(value: int) -> str:
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.2f} MiB"
    if value >= 1024:
        return f"{value / 1024:.1f} KiB"
    return f"{value} B"


def startup_status(rows_by_path: dict[str, MdFile], config: dict[str, Any]) -> tuple[list[str], int, int]:
    lines: list[str] = []
    total = 0
    for path in config.get("startup_files", []):
        row = rows_by_path.get(path)
        if row is None:
            lines.append(f"| `{path}` | missing | n/a | Missing |")
            continue
        total += row.size
        status = "OK" if not row.over_budget else f"Over by {format_bytes(row.over_by)}"
        lines.append(f"| `{path}` | {format_bytes(row.size)} | {format_bytes(row.budget)} | {status} |")
    target = config["budgets_bytes"]["startup_pack_total"]
    return lines, total, target


def render_report(rows: list[MdFile], config: dict[str, Any], top: int) -> str:
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows_by_path = {row.path: row for row in rows}
    over = [row for row in rows if row.over_budget]
    over_sorted = sorted(over, key=lambda row: (row.over_by, row.size), reverse=True)
    role_counts = Counter(row.role for row in rows)
    over_counts = Counter(row.role for row in over)
    startup_lines, startup_total, startup_target = startup_status(rows_by_path, config)
    startup_ok = startup_total <= startup_target

    out: list[str] = [
        "# Repository Context Budget Audit",
        "",
        f"Generated UTC: {generated}",
        "",
        "This report is generated from file metadata. It is a navigation and",
        "maintenance artifact, not a project verdict.",
        "",
        "## Summary",
        "",
        f"- Markdown files scanned: `{len(rows)}`",
        f"- Over-budget Markdown files: `{len(over)}`",
        f"- Startup pack size: `{format_bytes(startup_total)}` / `{format_bytes(startup_target)}`",
        f"- Startup pack status: `{'OK' if startup_ok else 'OVER BUDGET'}`",
        "",
        "## Startup Pack",
        "",
        "| File | Size | Budget | Status |",
        "|---|---:|---:|---|",
        *startup_lines,
        "",
        "## Role Counts",
        "",
        "| Role | Files | Over Budget |",
        "|---|---:|---:|",
    ]

    for role in sorted(role_counts):
        out.append(f"| `{role}` | {role_counts[role]} | {over_counts[role]} |")

    out.extend(
        [
            "",
            f"## Largest Over-Budget Files (Top {min(top, len(over_sorted))})",
            "",
            "| File | Role | Size | Budget | Over By |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in over_sorted[:top]:
        out.append(
            f"| `{row.path}` | `{row.role}` | {format_bytes(row.size)} | "
            f"{format_bytes(row.budget)} | {format_bytes(row.over_by)} |"
        )

    if not over_sorted:
        out.append("| none | n/a | n/a | n/a | n/a |")

    out.extend(
        [
            "",
            "## Recommended Handling",
            "",
            "- Keep startup files as route maps, not content stores.",
            "- Add compact indexes before expanding long memory or state files.",
            "- Treat `var/`, upload packs, logs, outputs, screenshots, and raw",
            "  source archives as targeted artifacts.",
            "- Use this report to decide what needs an index; do not automatically",
            "  move or delete files just because they are large.",
            "",
        ]
    )
    return "\n".join(out)


def main() -> int:
    global ROOT, CONFIG_PATH
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Workspace to scan (default: the folder above tools/).")
    parser.add_argument(
        "--config",
        type=Path,
        help="Budget config JSON (default: <root>/context/context_budget.json; built-in defaults if missing).",
    )
    parser.add_argument("--report", type=Path, help="Write a Markdown report to this path.")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP, help="Number of over-budget files to show.")
    parser.add_argument(
        "--fail-on-over-budget",
        action="store_true",
        help="Exit nonzero when any budget violation or startup-pack violation exists.",
    )
    args = parser.parse_args()
    ROOT = args.root.expanduser().resolve()
    CONFIG_PATH = args.config.expanduser().resolve() if args.config else ROOT / "context" / "context_budget.json"

    config = load_config()
    rows = collect(config)
    report = render_report(rows, config, args.top)

    if args.report:
        report_path = args.report if args.report.is_absolute() else ROOT / args.report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        try:
            shown = report_path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            shown = str(report_path)
        print(f"Wrote {shown}")
    else:
        print(report)

    rows_by_path = {row.path: row for row in rows}
    startup_total = sum(
        rows_by_path[path].size for path in config.get("startup_files", []) if path in rows_by_path
    )
    startup_ok = startup_total <= config["budgets_bytes"]["startup_pack_total"]
    has_over = any(row.over_budget for row in rows)
    if args.fail_on_over_budget and (has_over or not startup_ok):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
