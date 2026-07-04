#!/usr/bin/env python3
"""Lock the BOOT.md line limit."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from context_integrity_check import run_checks
from test_context_integrity import make_fixture


class BootLineLimitTests(unittest.TestCase):
    def test_boot_over_80_lines_fails(self) -> None:
        with make_fixture() as tmp:
            root = Path(tmp)
            (root / "BOOT.md").write_text("\n".join(f"line {i}" for i in range(81)) + "\n", encoding="utf-8")
            result = run_checks(root)
            self.assertEqual(result["summary"]["verdict"], "CONTEXT_INTEGRITY_FAIL_BOOT_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
