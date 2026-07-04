#!/usr/bin/env python3
"""Detect recursive startup-entry files by filename and content patterns."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from context_common import artifact_id, read_json, relpath, utc_now, write_csv, write_json
from governor_common import GOVERNOR_AUDIT_DIR_REL, append_governor_gap, ensure_governor_dirs, is_allowlisted


SCAN_EXTS = {".md", ".txt", ".json"}
SKIP_PARTS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
RISK_PATTERNS = [
    ("BOOT_FOR_BOOT", re.compile(r"BOOT[_ -]?FOR[_ -]?BOOT", re.I)),
    ("START_HERE_FOR_START_HERE", re.compile(r"START[_ -]?HERE[_ -]?FOR[_ -]?START[_ -]?HERE", re.I)),
    ("ENTRY_FOR_ENTRY", re.compile(r"ENTRY(?:POINT)?[_ -]?FOR[_ -]?ENTRY(?:POINT)?", re.I)),
    ("README_FOR_BOOT", re.compile(r"README[_ -]?FOR[_ -]?BOOT", re.I)),
    ("SUMMARY_OF_ENTRYPOINT", re.compile(r"SUMMARY[_ -]?OF[_ -]?ENTRY(?:POINT)?", re.I)),
    ("START_HERE_V2", re.compile(r"START[_ -]?HERE(?:[_ -]?V?2|[_ -]?新版|[_ -]?完整版)", re.I)),
    ("BOOT_V2", re.compile(r"BOOT(?:[_ -]?V?2|[_ -]?新版|[_ -]?完整版)", re.I)),
    ("COMPLETE_STARTUP_GUIDE", re.compile(r"更完整的启动说明|项目总入口完整版|agent 启动大全|启动文件摘要|继续摘要入口|入口说明书|更短入口|更全入口|入口的入口")),
]


FIELDS = ["path", "risk_id", "matched_on", "matched_text", "allowed", "severity", "recommendation"]


def scan_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for child in sorted(root.iterdir()):
        if child.is_file() and child.suffix.lower() in SCAN_EXTS:
            paths.append(child)
    for base in [root / "context", root / "docs"]:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SCAN_EXTS:
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            paths.append(path)
    return sorted(set(paths))


def match_file(root: Path, path: Path, allowlist: dict[str, Any]) -> list[dict[str, str]]:
    rel = relpath(root, path)
    text = ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:60000]
    except Exception:
        text = ""
    haystacks = [("filename", path.name), ("content", text)]
    rows: list[dict[str, str]] = []
    for risk_id, pattern in RISK_PATTERNS:
        for matched_on, value in haystacks:
            match = pattern.search(value)
            if not match:
                continue
            allowed = is_allowlisted(root, rel, allowlist)
            rows.append(
                {
                    "path": rel,
                    "risk_id": risk_id,
                    "matched_on": matched_on,
                    "matched_text": match.group(0)[:160],
                    "allowed": "TRUE" if allowed else "FALSE",
                    "severity": "INFO" if allowed else "HIGH",
                    "recommendation": "allowed_documentation_or_active_boot" if allowed else "move to quarantine or rename into a non-entry reference",
                }
            )
    return rows


def run(root: Path) -> dict[str, Any]:
    ensure_governor_dirs(root)
    allowlist_path = root / "context/RECURSIVE_ENTRY_ALLOWLIST.json"
    allowlist = read_json(allowlist_path, {"allowed_paths": []})
    rows: list[dict[str, str]] = []
    for path in scan_paths(root):
        rows.extend(match_file(root, path, allowlist))
    risky = [row for row in rows if row["allowed"] != "TRUE"]
    for row in risky:
        append_governor_gap(
            root,
            {
                "gap_id": artifact_id("recursive_entry", row["path"] + row["risk_id"]),
                "phase": "recursive_entry_detector",
                "project_id": "default",
                "artifact_path": row["path"],
                "gap_type": row["risk_id"],
                "severity": "HIGH",
                "blocking_level": "BLOCKING",
                "observed_status": row["matched_text"],
                "expected_status": "no recursive entrypoint variants outside allowlist",
                "next_action": "move to context/quarantine or rewrite as a normal reference file",
                "notes": row["recommendation"],
            },
        )
    scan_path = root / GOVERNOR_AUDIT_DIR_REL / "recursive_entry_scan.csv"
    summary_path = root / GOVERNOR_AUDIT_DIR_REL / "recursive_entry_summary.json"
    verdict_path = root / GOVERNOR_AUDIT_DIR_REL / "recursive_entry_verdict.json"
    write_csv(scan_path, FIELDS, rows)
    summary = {
        "script": "recursive_entry_detector.py",
        "scanned_files": len(scan_paths(root)),
        "matches": len(rows),
        "risky_matches": len(risky),
        "allowlist_path": relpath(root, allowlist_path),
        "updated_at_utc": utc_now(),
    }
    verdict = {
        "script": "recursive_entry_detector.py",
        "verdict": "RECURSIVE_ENTRY_PASS" if not risky else "RECURSIVE_ENTRY_FAIL",
        "hard_blocker": bool(risky),
        "risky_matches": len(risky),
        "updated_at_utc": utc_now(),
    }
    write_json(summary_path, summary)
    write_json(verdict_path, verdict)
    return verdict


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()
    result = run(Path(args.root).expanduser().resolve())
    print(f"recursive entry verdict: {result['verdict']}")
    return 0 if result["verdict"] == "RECURSIVE_ENTRY_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
