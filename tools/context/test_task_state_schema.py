#!/usr/bin/env python3
"""Tests for compact task state and pointer schema checks."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from context_common import write_json
from context_integrity_check import run_checks
from test_context_integrity import make_fixture


class TaskStateSchemaTests(unittest.TestCase):
    def test_missing_runner_pointer_fails(self) -> None:
        with make_fixture() as tmp:
            root = Path(tmp)
            write_json(
                root / "context/TASK_STATE.json",
                {
                    "current_runner": "tools/context/missing.sh",
                    "latest_verdict_path": "context/CURRENT_VERDICT.json",
                    "latest_gap_queue_path": "var/context_control_2026_06_23/gap_queue.csv",
                    "holdout_status": "LOCKED",
                },
            )
            result = run_checks(root)
            self.assertEqual(result["summary"]["verdict"], "CONTEXT_INTEGRITY_FAIL_MISSING_POINTER")

    def test_unlocked_holdout_fails(self) -> None:
        with make_fixture() as tmp:
            root = Path(tmp)
            write_json(
                root / "context/TASK_STATE.json",
                {
                    "current_runner": "tools/context/run_context_control_all.sh",
                    "latest_verdict_path": "context/CURRENT_VERDICT.json",
                    "latest_gap_queue_path": "var/context_control_2026_06_23/gap_queue.csv",
                    "holdout_status": "UNLOCKED",
                },
            )
            result = run_checks(root)
            self.assertEqual(result["summary"]["verdict"], "CONTEXT_INTEGRITY_FAIL_HOLDOUT_RISK")

    def test_overlong_task_state_fails(self) -> None:
        with make_fixture() as tmp:
            root = Path(tmp)
            payload = {
                "current_runner": "tools/context/run_context_control_all.sh",
                "latest_verdict_path": "context/CURRENT_VERDICT.json",
                "latest_gap_queue_path": "var/context_control_2026_06_23/gap_queue.csv",
                "holdout_status": "LOCKED",
                "padding": {str(i): i for i in range(201)},
            }
            write_json(root / "context/TASK_STATE.json", payload)
            result = run_checks(root)
            self.assertEqual(result["summary"]["verdict"], "CONTEXT_INTEGRITY_FAIL_STATE_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
