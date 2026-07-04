#!/usr/bin/env python3
"""Tests for authority conflict behavior."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from context_common import write_csv
from context_integrity_check import authority_winner, run_checks
from test_context_integrity import make_fixture


class AuthorityConflictTests(unittest.TestCase):
    def test_highest_authority_wins(self) -> None:
        winner = authority_winner(
            [
                {"path": "summary.md", "authority_level": "60"},
                {"path": "manifest.csv", "authority_level": "95"},
                {"path": "notes.md", "authority_level": "40"},
            ]
        )
        self.assertEqual(winner["path"], "manifest.csv")

    def test_generated_summary_cannot_be_source_of_truth_above_source_ceiling(self) -> None:
        with make_fixture() as tmp:
            root = Path(tmp)
            write_csv(
                root / "context/indexes/FILE_INDEX.csv",
                ["path", "artifact_type", "authority_level", "source_of_truth"],
                [{"path": "BOOT.md", "artifact_type": "boot", "authority_level": "99", "source_of_truth": "TRUE"}],
            )
            result = run_checks(root)
            self.assertEqual(result["summary"]["verdict"], "CONTEXT_INTEGRITY_FAIL_SEMANTIC_DRIFT")


if __name__ == "__main__":
    unittest.main()
