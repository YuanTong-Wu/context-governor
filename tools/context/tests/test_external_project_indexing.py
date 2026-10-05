#!/usr/bin/env python3
import csv
import shutil
import tempfile
from pathlib import Path

from test_common import assert_true, read_json, run_cmd


GLOBAL_FILES = [
    Path("context/global/PROJECT_REGISTRY.json"),
    Path("context/global/ACTIVE_PROJECT.json"),
    Path("context/global/PROJECTS.csv"),
    # startup_budget_test.py rewrites these; the caller's results are put back.
    Path("var/context_governor_2026_06_24/audit/startup_budget_check.csv"),
    Path("var/context_governor_2026_06_24/audit/startup_budget_summary.json"),
    Path("var/context_governor_2026_06_24/audit/startup_budget_verdict.json"),
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
            bundle = root / f"context/generated/startup_bundles/{project_id}_STARTUP_BUNDLE.md"
            assert_true(bundle.exists(), "external startup bundle should exist")

            # The startup budget reads this project's own views and full-index paths.
            budget_cmd = ["python3", "tools/context/startup_budget_test.py", "--root", str(root), "--project-id", project_id]
            verdict_path = root / "var/context_governor_2026_06_24/audit/startup_budget_verdict.json"
            run_cmd(budget_cmd, root, timeout=120)
            verdict = read_json(verdict_path)
            assert_true(verdict.get("project_id") == project_id, "startup budget should check the external project")
            assert_true(verdict.get("verdict") == "STARTUP_BUDGET_PASS", f"external project startup budget should pass: {verdict}")

            # A leak of this project's full index into its bundle must block.
            original = bundle.read_text(encoding="utf-8")
            bundle.write_text(original + f"\n- leaked: `context/projects/{project_id}/indexes/FILE_INDEX.csv`\n", encoding="utf-8")
            run_cmd(budget_cmd, root, expect=2, timeout=120)
            verdict = read_json(verdict_path)
            assert_true(verdict.get("verdict") == "STARTUP_BUDGET_FAIL_FULL_INDEX_INCLUDED", f"project full-index leak should block: {verdict}")
            bundle.write_text(original, encoding="utf-8")
    finally:
        restore_files(root, backups)
        shutil.rmtree(root / f"context/projects/{project_id}", ignore_errors=True)
        for suffix in ("STARTUP_BUNDLE.md", "STARTUP_BUNDLE_MANIFEST.csv", "STARTUP_BUDGET_AUDIT.json"):
            (root / f"context/generated/startup_bundles/{project_id}_{suffix}").unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
