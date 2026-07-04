#!/usr/bin/env python3
"""Shared utilities for the context microkernel scripts."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CONTROL_DIR_REL = Path("var/context_control_2026_06_23")
AUDIT_DIR_REL = CONTROL_DIR_REL / "audit"
REPORT_DIR_REL = CONTROL_DIR_REL / "reports"
CONTEXT_DIR_REL = Path("context")
INDEX_DIR_REL = CONTEXT_DIR_REL / "indexes"
GENERATED_DIR_REL = CONTEXT_DIR_REL / "generated"
LOG_DIR_REL = CONTEXT_DIR_REL / "logs"

GAP_QUEUE_FIELDS = [
    "gap_id",
    "phase",
    "artifact_path",
    "gap_type",
    "severity",
    "blocking_level",
    "observed_status",
    "expected_status",
    "auto_repairable",
    "repair_attempted",
    "repair_result",
    "next_action",
    "created_at_utc",
    "notes",
]

BLOCKED_FIELDS = [
    "blocked_id",
    "phase",
    "artifact_path",
    "reason",
    "severity",
    "created_at_utc",
    "next_action",
    "notes",
]


def project_root(default_file: str | None = None) -> Path:
    if default_file:
        return Path(default_file).resolve().parents[2]
    return Path(__file__).resolve().parents[2]


def coerce_root(root: str | Path | None = None) -> Path:
    return Path(root).expanduser().resolve() if root else project_root(__file__)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dirs(root: Path) -> None:
    for rel in [
        CONTEXT_DIR_REL,
        INDEX_DIR_REL,
        GENERATED_DIR_REL,
        LOG_DIR_REL,
        CONTEXT_DIR_REL / "schemas",
        CONTEXT_DIR_REL / "checks",
        Path("tools/context"),
        CONTROL_DIR_REL,
        AUDIT_DIR_REL,
        REPORT_DIR_REL,
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)


def relpath(root: Path, path: str | Path) -> str:
    p = Path(path)
    try:
        return str(p.resolve().relative_to(root.resolve()))
    except Exception:
        return str(p)


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: str | Path, default: Any | None = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    with p.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(json_bytes(data))


def write_json_with_self_sha(path: str | Path, data: dict[str, Any], field: str = "sha256_self") -> str:
    body = dict(data)
    body[field] = ""
    digest = hashlib.sha256(json_bytes(body)).hexdigest()
    body[field] = digest
    write_json(path, body)
    return digest


def read_csv(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: str | Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def append_jsonl(path: str | Path, row: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def line_count(path: str | Path) -> int:
    p = Path(path)
    if not p.exists():
        return 0
    with p.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def char_count(path: str | Path) -> int:
    p = Path(path)
    if not p.exists():
        return 0
    return len(p.read_text(encoding="utf-8", errors="replace"))


def file_mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def classify_artifact(path: Path) -> str:
    name = path.name.lower()
    text = str(path).lower()
    if name == "boot.md":
        return "boot"
    if name == "system_invariants.json":
        return "invariant"
    if name == "task_state.json":
        return "task_state"
    if name in {"current_verdict.json", "verdict.json"}:
        return "verdict"
    if name == "summary.json" or name.endswith("_summary.json"):
        return "summary"
    if "manifest" in name:
        return "manifest"
    if "gap_queue" in name:
        return "gap_queue"
    if "blocked_reason" in name:
        return "blocked_reason"
    if "schema" in text or path.suffix.lower() in {".jsonschema"}:
        return "schema"
    if path.suffix.lower() in {".py", ".sh"} and "tools" in path.parts:
        return "runner"
    if "runbook" in name or "manual" in name:
        return "runbook"
    if "case_card" in name:
        return "case_card"
    if "case" in name or "sample" in name:
        return "case_package"
    if "evidence" in name:
        return "evidence_manifest"
    if "raw" in name or "archive" in name:
        return "raw_archive"
    if "dataset" in name or "timeseries" in name:
        return "dataset"
    if "results" in name or "metrics" in name or "结果" in name:
        return "results"
    if "leakage" in name:
        return "leakage_audit"
    if path.suffix.lower() == ".md":
        return "report"
    return "unknown"


def infer_phase(path: Path) -> str:
    text = str(path).lower()
    for key in [
        "context_control",
        "phase2",
        "phase1",
    ]:
        if key in text:
            return key
    return "unspecified"


def infer_authority(path: Path, artifact_type: str) -> int:
    name = path.name.lower()
    text = str(path).lower()
    if artifact_type == "invariant":
        return 70
    if artifact_type in {"summary", "verdict"}:
        return 80
    if artifact_type == "manifest":
        return 95 if "raw" in name else 90
    if artifact_type == "schema":
        return 75
    if artifact_type == "runner":
        return 85
    if "official" in text and artifact_type in {"raw_archive", "evidence_manifest"}:
        return 100
    if artifact_type in {"raw_archive", "evidence_manifest"}:
        return 90
    if artifact_type == "report":
        return 60
    if "archive" in text:
        return 40
    return 50


def read_policy_for(path: Path, artifact_type: str) -> str:
    text = str(path).lower()
    if "holdout" in text or "sealed" in text or "封存" in text:
        return "metadata_only_locked"
    if artifact_type in {"raw_archive", "dataset", "results"}:
        return "metadata_only_unless_audit"
    if artifact_type == "boot":
        return "startup_read"
    return "read_when_relevant"


def write_policy_for(artifact_type: str) -> str:
    if artifact_type in {"raw_archive", "evidence_manifest", "dataset", "results"}:
        return "do_not_modify"
    if artifact_type == "boot":
        return "generated_only"
    if artifact_type in {"task_state", "verdict", "summary", "manifest", "gap_queue", "blocked_reason"}:
        return "script_generated"
    return "manual_or_script_scoped"


def should_scan_file(path: Path) -> bool:
    suffixes = {".md", ".csv", ".json", ".jsonl", ".py", ".sh", ".parquet", ".txt"}
    if path.suffix.lower() not in suffixes:
        return False
    skip_parts = {".git", "__pycache__", ".venv", "node_modules"}
    return not any(part in skip_parts for part in path.parts)


def artifact_id(prefix: str, path: str | Path) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", str(path)).strip("_").lower()
    return f"{prefix}_{sha256_text(clean)[:12]}"


def write_script_audit(
    root: Path,
    script_name: str,
    summary: dict[str, Any],
    verdict: dict[str, Any],
    manifest_rows: list[dict[str, Any]] | None = None,
) -> None:
    ensure_dirs(root)
    audit = root / AUDIT_DIR_REL
    write_json(audit / f"{script_name}_summary.json", summary)
    write_json(audit / f"{script_name}_verdict.json", verdict)
    if manifest_rows is not None:
        fields = ["artifact_path", "artifact_role", "sha256", "created_at_utc", "notes"]
        write_csv(audit / f"{script_name}_manifest.csv", fields, manifest_rows)


def ensure_control_csvs(root: Path) -> None:
    gap_path = root / CONTROL_DIR_REL / "gap_queue.csv"
    blocked_path = root / CONTROL_DIR_REL / "blocked_reason.csv"
    if not gap_path.exists():
        write_csv(gap_path, GAP_QUEUE_FIELDS, [])
    if not blocked_path.exists():
        write_csv(blocked_path, BLOCKED_FIELDS, [])


def append_gap(root: Path, row: dict[str, Any]) -> None:
    ensure_control_csvs(root)
    path = root / CONTROL_DIR_REL / "gap_queue.csv"
    rows = read_csv(path)
    row = dict(row)
    row.setdefault("gap_id", artifact_id("gap", json.dumps(row, sort_keys=True, ensure_ascii=False)))
    row.setdefault("created_at_utc", utc_now())
    rows.append(row)
    write_csv(path, GAP_QUEUE_FIELDS, rows)


def append_blocked(root: Path, row: dict[str, Any]) -> None:
    ensure_control_csvs(root)
    path = root / CONTROL_DIR_REL / "blocked_reason.csv"
    rows = read_csv(path)
    row = dict(row)
    row.setdefault("blocked_id", artifact_id("blocked", json.dumps(row, sort_keys=True, ensure_ascii=False)))
    row.setdefault("created_at_utc", utc_now())
    rows.append(row)
    write_csv(path, BLOCKED_FIELDS, rows)


def copy_to_quarantine(root: Path, path: Path, reason: str) -> dict[str, str]:
    qdir = root / CONTEXT_DIR_REL / "quarantine"
    qdir.mkdir(parents=True, exist_ok=True)
    digest = sha256_file(path)
    target = qdir / f"{path.name}.{digest[:12]}.quarantined"
    shutil.move(str(path), str(target))
    return {
        "original_path": relpath(root, path),
        "quarantine_path": relpath(root, target),
        "sha256": digest,
        "reason": reason,
        "created_at_utc": utc_now(),
    }
