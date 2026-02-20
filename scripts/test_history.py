#!/usr/bin/env python3
"""Read-only test history/diff helper for Ears."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--history", nargs="?", const=True)
    parser.add_argument("--diff", nargs="+")
    known, pytest_args = parser.parse_known_args(argv)

    test_env_python = ".artifacts/test/test-env/bin/python"
    python_cmd = test_env_python if os.path.exists(test_env_python) else "python3"

    cmd = [python_cmd, "-m", "pytest"]
    has_test_target = any(not arg.startswith("-") for arg in pytest_args)
    if not has_test_target:
        cmd.append("tests/ears_tuner/")

    cmd.extend(pytest_args)
    if known.history is not None:
        if known.history is True:
            cmd.append("--history")
        else:
            cmd.extend(["--history", str(known.history)])
    if known.diff:
        cmd.append("--diff")
        cmd.extend(known.diff)

    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
