#!/usr/bin/env python3
"""Verify that multiple projects can be registered and active project can switch."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from test_common import REPO_ROOT, assert_true, read_json, run_cmd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(REPO_ROOT))
    args = parser.parse_args()
    repo = Path(args.root).expanduser().resolve()
    script = repo / "tools/context/project/init_project_context.py"

    with tempfile.TemporaryDirectory(prefix="context-governor-switch-") as tmp:
        tmp_root = Path(tmp)
        run_cmd(
            [
                "python3",
                str(script),
                "--root",
                str(tmp_root),
                "--project-id",
                "alpha",
                "--project-root",
                str(tmp_root / "alpha-work"),
                "--project-name",
                "Alpha Project",
            ],
            repo,
        )
        run_cmd(
            [
                "python3",
                str(script),
                "--root",
                str(tmp_root),
                "--project-id",
                "beta",
                "--project-root",
                str(tmp_root / "beta-work"),
                "--project-name",
                "Beta Project",
                "--activate",
            ],
            repo,
        )
        registry = read_json(tmp_root / "context/global/PROJECT_REGISTRY.json")
        active = read_json(tmp_root / "context/global/ACTIVE_PROJECT.json")
        assert_true("alpha" in registry.get("projects", {}), "alpha project missing")
        assert_true("beta" in registry.get("projects", {}), "beta project missing")
        assert_true(active.get("active_project_id") == "beta", "active project did not switch to beta")
        assert_true((tmp_root / "context/projects/beta/BOOT.md").exists(), "beta local boot missing")
    print("active project switch test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

