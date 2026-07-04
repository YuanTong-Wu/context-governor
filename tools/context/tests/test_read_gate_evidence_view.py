#!/usr/bin/env python3
import json
from pathlib import Path

from test_common import assert_true, run_cmd


def read_gate(root: Path, rel_path: str) -> dict[str, object]:
    result = run_cmd(
        [
            "python3",
            "tools/context/read_gate/read_context_file.py",
            rel_path,
            "--root",
            str(root),
            "--project-id",
            "default",
            "--reason",
            "p0-test",
            "--max-chars",
            "20000",
        ],
        root,
        timeout=120,
    )
    return json.loads(result.stdout)


def rebuild_indexes(root: Path) -> None:
    for script in ("build_file_index.py", "build_evidence_index.py", "build_index_views.py"):
        run_cmd(
            ["python3", f"tools/context/{script}", "--root", str(root), "--project-id", "default"],
            root,
            timeout=120,
        )


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    raw_rel = "var/context_governor_p0_fix_2026_06_24/raw_archive_evidence_test.json"
    raw_path = root / raw_rel
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text('{"official_evidence": true}\n', encoding="utf-8")
    try:
        rebuild_indexes(root)
        view = read_gate(root, "context/indexes/views/EVIDENCE_INDEX_VIEW.csv")
        assert_true(view.get("allowed") is True, "evidence view should be readable")
        assert_true(view.get("mode") == "content", "evidence view should return content")
        view_meta = view.get("metadata") or {}
        assert_true(view_meta.get("artifact_type") == "index_view", "view should be classified as index view")

        raw = read_gate(root, raw_rel)
        assert_true(raw.get("allowed") is True, "raw evidence pointer should be allowed")
        assert_true(raw.get("mode") == "pointer_only", "raw evidence should default to pointer-only")
        raw_meta = raw.get("metadata") or {}
        assert_true(raw_meta.get("source_index") == "evidence", "raw evidence should be resolved through evidence index")
        assert_true(raw_meta.get("artifact_type") == "raw_archive", "raw evidence should keep raw archive artifact type")
    finally:
        raw_path.unlink(missing_ok=True)
        rebuild_indexes(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
