#!/usr/bin/env python3
"""Lock the recursive entry file ban."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from context_integrity_check import run_checks
from test_context_integrity import make_fixture


class RecursiveEntryTests(unittest.TestCase):
    def test_recursive_entry_file_fails(self) -> None:
        with make_fixture() as tmp:
            root = Path(tmp)
            (root / "BOOT_FOR_BOOT.md").write_text("# bad\n", encoding="utf-8")
            result = run_checks(root)
            self.assertEqual(result["summary"]["verdict"], "CONTEXT_INTEGRITY_FAIL_RECURSIVE_ENTRY")


if __name__ == "__main__":
    unittest.main()
