#!/usr/bin/env python3
import csv
import shutil
import tempfile
from pathlib import Path

from test_common import assert_true, run_cmd


GLOBAL_FILES = [
    Path("context/global/PROJECT_REGISTRY.json"),
    Path("context/global/ACTIVE_PROJECT.json"),
    Path("context/global/PROJECTS.csv"),
]


def backup_files(root: Path) -> dict[Path, bytes | None]:
    return {rel: (root / rel).read_bytes() if (root / rel).exists() else None for rel in GLOBAL_FILES}


def restore_files(root: Path, backups: dict[Path, bytes | None]) -> None:
    for rel, data in backups.items():
        path = root / rel
        if data is None:
            path.unlink(missing_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    project_id = "p0_external_index_test"
    backups = backup_files(root)
    try:
        with tempfile.TemporaryDirectory(prefix="context-governor-external-project-") as tmp:
            external = Path(tmp)
            (external / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
            (external / "beta.json").write_text('{"beta": true}\n', encoding="utf-8")
            (external / "notes.txt").write_text("notes\n", encoding="utf-8")

            run_cmd(
                [
                    "python3",
                    "tools/context/project/init_project_context.py",
                    "--root",
                    str(root),
                    "--project-id",
                    project_id,
                    "--project-root",
                    str(external),
                    "--project-name",
                    "P0 External Index Test",
                    "--activate",
                ],
                root,
                timeout=120,
            )
            for script in (
                "build_file_index.py",
                "build_runner_index.py",
                "build_case_index.py",
                "build_evidence_index.py",
                "build_gap_index.py",
            ):
                run_cmd(
                    ["python3", f"tools/context/{script}", "--root", str(root), "--project-id", project_id],
                    root,
                    timeout=120,
                )
            run_cmd(
                ["python3", "tools/context/build_index_views.py", "--root", str(root), "--project-id", project_id],
                root,
                timeout=120,
            )
            run_cmd(
                ["python3", "tools/context/build_startup_bundle.py", "--root", str(root), "--project-id", project_id],
                root,
                timeout=120,
            )

            rows = read_rows(root / f"context/projects/{project_id}/indexes/FILE_INDEX.csv")
            assert_true(len(rows) == 3, "external file index should only include external project files")
            assert_true(sorted(row["path"] for row in rows) == ["alpha.md", "beta.json", "notes.txt"], "external paths should be project-relative")
            assert_true({row["project_id"] for row in rows} == {project_id}, "all rows should carry external project id")

            query = run_cmd(
                [
                    "python3",
                    "tools/context/query_index.py",
                    "--root",
                    str(root),
                    "--index",
                    "file",
                    "--project-id",
                    project_id,
                    "--limit",
                    "20",
                ],
                root,
                timeout=120,
            )
            lines = [line for line in query.stdout.splitlines() if line.strip()]
            assert_true(len(lines) == 4, "query should return header plus three rows")
            assert_true("alpha.md" in query.stdout and "beta.json" in query.stdout and "notes.txt" in query.stdout, "query output should include external files")
            assert_true((root / f"context/projects/{project_id}/indexes/views/FILE_INDEX_VIEW.csv").exists(), "external file view should exist")
            assert_true((root / f"context/generated/startup_bundles/{project_id}_STARTUP_BUNDLE.md").exists(), "external startup bundle should exist")
    finally:
        restore_files(root, backups)
        shutil.rmtree(root / f"context/projects/{project_id}", ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
