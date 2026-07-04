#!/usr/bin/env python3
from pathlib import Path

from test_common import assert_true, run_cmd


def bundle_from_stdout(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.startswith("STARTUP_BUNDLE="):
            return line.split("=", 1)[1]
    raise AssertionError("STARTUP_BUNDLE missing from start_project output")


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    outputs = []
    for _ in range(2):
        result = run_cmd(
            ["bash", "tools/context/start_project.sh", "default", "--root", str(root)],
            root,
            timeout=180,
        )
        outputs.append(result.stdout)

    for stdout in outputs:
        assert_true("PROJECT_ID=default" in stdout, "start_project should print project id")
        assert_true("STARTUP_BUNDLE=" in stdout, "start_project should print startup bundle")
        assert_true("CURRENT_RUNNER=" in stdout, "start_project should print current runner")
        assert_true("NEXT_ACTION=" in stdout, "start_project should print next action")
        assert_true("READ_FIRST=" in stdout, "start_project should print read-first files")
        assert_true((root / bundle_from_stdout(stdout)).exists(), "startup bundle should exist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
