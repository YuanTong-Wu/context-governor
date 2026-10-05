#!/usr/bin/env python3
"""End-to-end tests for Context Governor and Keeper.

Each run builds a fresh demo workspace in a temporary directory with
scripts/make_workspace.sh and runs every check inside it, so this repository is
never written to. Run from the repository root:

    python3 -m unittest discover -s tests -v

Set KEEP_WORKSPACE=1 to keep the temporary workspace for inspection.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
UNIT_TESTS = [
    "tools/context/test_authority_conflict_policy.py",
    "tools/context/test_boot_line_limit.py",
    "tools/context/test_context_integrity.py",
    "tools/context/test_no_recursive_entry.py",
    "tools/context/test_task_state_schema.py",
]
GOVERNOR_VERDICT = "var/context_governor_2026_06_24/verdict.json"
CONTROL_VERDICT = "var/context_control_2026_06_23/verdict.json"


def run(args: list[str], cwd: Path, env: dict[str, str], timeout: int = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout)


def describe(proc: subprocess.CompletedProcess[str]) -> str:
    return f"exit={proc.returncode}\n--- stdout ---\n{proc.stdout[-4000:]}\n--- stderr ---\n{proc.stderr[-4000:]}"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class WorkspaceTests(unittest.TestCase):
    tmp: str
    ws: Path
    env: dict[str, str]
    governor: subprocess.CompletedProcess[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.mkdtemp(prefix="context-governor-test-")
        cls.ws = Path(cls.tmp) / "workspace"
        cls.env = dict(os.environ, PYTHON=sys.executable, PYTHONDONTWRITEBYTECODE="1")
        made = run(["bash", str(REPO / "scripts/make_workspace.sh"), str(cls.ws)], REPO, cls.env)
        if made.returncode != 0:
            raise RuntimeError("make_workspace.sh failed\n" + describe(made))
        cls.governor = run(["bash", "tools/context/run_context_governor_all.sh", "--root", str(cls.ws)], cls.ws, cls.env)

    @classmethod
    def tearDownClass(cls) -> None:
        if os.environ.get("KEEP_WORKSPACE"):
            print(f"\nworkspace kept at {cls.ws}", file=sys.stderr)
        else:
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def py(self, *args: str, expect: int | None = 0) -> subprocess.CompletedProcess[str]:
        proc = run([sys.executable, *args], self.ws, self.env)
        if expect is not None:
            self.assertEqual(proc.returncode, expect, describe(proc))
        return proc

    def test_01_unit_tests(self) -> None:
        for rel in UNIT_TESTS:
            with self.subTest(test=rel):
                self.py(rel)

    def test_02_governor_run_is_non_blocking(self) -> None:
        self.assertEqual(self.governor.returncode, 0, describe(self.governor))
        verdict = read_json(self.ws / GOVERNOR_VERDICT)
        self.assertEqual(verdict["verdict"], "MULTI_PROJECT_CONTEXT_GOVERNOR_BUILT_AND_VERIFIED")
        self.assertFalse(verdict["hard_blocker"])
        with (self.ws / "var/context_governor_2026_06_24/audit/governor_run_steps.csv").open(encoding="utf-8") as handle:
            steps = list(csv.DictReader(handle))
        # 17 steps, plus bootstrap_task_state on a fresh workspace.
        self.assertIn(len(steps), {17, 18})
        self.assertEqual({row["status"] for row in steps}, {"PASS"})
        tests = read_json(self.ws / "var/context_governor_2026_06_24/audit/context_tests_summary.json")
        self.assertEqual(tests["tests"], 16)
        self.assertEqual(tests["failures"], 0)

    def test_03_startup_context_stays_small(self) -> None:
        boot = (self.ws / "BOOT.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(boot.splitlines()), 80)
        self.assertLessEqual(len(boot), 4000)
        self.assertIn("Holdout samples must remain locked", boot)
        bundle = (self.ws / "context/generated/startup_bundles/default_STARTUP_BUNDLE.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(bundle), 12000)
        for full_index in ["FILE_INDEX.csv", "RUNNER_INDEX.csv", "CASE_INDEX.csv", "EVIDENCE_INDEX.csv", "GAP_INDEX.csv"]:
            self.assertNotIn(f"context/indexes/{full_index}", bundle)
        budget = read_json(self.ws / "var/context_governor_2026_06_24/audit/startup_budget_verdict.json")
        self.assertEqual(budget["verdict"], "STARTUP_BUDGET_PASS")

    def test_04_registry_stores_relative_project_root(self) -> None:
        registry = read_json(self.ws / "context/global/PROJECT_REGISTRY.json")
        self.assertEqual(registry["projects"]["default"]["project_root"], ".")
        self.assertNotIn(str(self.ws), (self.ws / "context/global/PROJECTS.csv").read_text(encoding="utf-8"))

    def test_05_read_gate(self) -> None:
        gate = "tools/context/read_gate/read_context_file.py"
        note = json.loads(self.py(gate, "notes/design_notes.md", "--root", str(self.ws)).stdout)
        self.assertEqual(note["mode"], "content")
        raw = json.loads(self.py(gate, "data/raw/source_archive.csv", "--root", str(self.ws), "--reason", "test").stdout)
        self.assertEqual(raw["mode"], "pointer_only")
        self.assertNotIn("content", raw)
        sealed = self.py(gate, "holdout/sealed_sample.md", "--root", str(self.ws), "--reason", "test", "--max-chars", "10", expect=2)
        self.assertIn("HOLDOUT_CONTENT_READ_DENIED", sealed.stdout)
        log = (self.ws / "context/read_logs/CONTEXT_READ_LOG.jsonl").read_text(encoding="utf-8")
        self.assertGreaterEqual(len(log.strip().splitlines()), 3)

    def test_06_forbidden_claim_from_config_blocks(self) -> None:
        boot_path = self.ws / "BOOT.md"
        original = boot_path.read_text(encoding="utf-8")
        try:
            boot_path.write_text(original + "Holdout samples are now unlocked.\n", encoding="utf-8")
            proc = self.py("tools/context/context_integrity_check.py", "--root", str(self.ws), expect=1)
            self.assertIn("FAIL_SEMANTIC_DRIFT", read_json(self.ws / "var/context_control_2026_06_23/audit/context_integrity_verdict.json")["verdict"], describe(proc))
        finally:
            boot_path.write_text(original, encoding="utf-8")
        self.py("tools/context/context_integrity_check.py", "--root", str(self.ws))

    def test_07_continue_refuses_governance_runner(self) -> None:
        proc = run(["bash", "tools/context/continue_project.sh", "default", "--root", str(self.ws)], self.ws, self.env)
        self.assertEqual(proc.returncode, 3, describe(proc))
        self.assertIn("recursive governor runner blocked", proc.stdout)

    def test_08_change_preflight(self) -> None:
        proc = self.py("tools/dev/preflight_change.py", "--root", str(self.ws), "--changed-file", "BOOT.md")
        self.assertEqual(proc.stdout.strip().splitlines()[-1], "RISK_REVIEW_REQUIRED")

    def test_09_control_run_is_non_blocking(self) -> None:
        proc = run(["bash", "tools/context/run_context_control_all.sh", "--root", str(self.ws)], self.ws, self.env)
        self.assertEqual(proc.returncode, 0, describe(proc))
        verdict = read_json(self.ws / CONTROL_VERDICT)
        self.assertFalse(verdict["hard_blocker"])
        self.assertEqual(verdict["integrity_source_path"], "var/context_control_2026_06_23/audit/context_integrity_verdict.json")

    def test_10_keeper(self) -> None:
        self.py("tools/keeper/tests/test_keeper.py")
        status = run(["./管家", "现在做到哪了"], self.ws, self.env)
        self.assertEqual(status.returncode, 0, describe(status))
        self.assertIn("当前项目：default", status.stdout)
        self.assertIn("holdout 状态：LOCKED", status.stdout)

    def test_11_markdown_budget_check(self) -> None:
        proc = self.py("tools/context_budget_check.py", "--root", str(self.ws), "--top", "5")
        self.assertIn("Startup pack status: `OK`", proc.stdout)


if __name__ == "__main__":
    unittest.main()
