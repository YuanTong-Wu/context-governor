#!/usr/bin/env python3
"""Small helpers for context governor tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def context_tools(root: Path) -> Path:
    return root / "tools/context"


def run_cmd(args: list[str], root: Path, expect: int | None = 0, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(args, cwd=root, text=True, capture_output=True, timeout=timeout)
    if expect is not None and proc.returncode != expect:
        sys.stderr.write(f"command failed: {' '.join(args)}\n")
        sys.stderr.write(f"expected: {expect}, got: {proc.returncode}\n")
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(1)
    return proc


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)

