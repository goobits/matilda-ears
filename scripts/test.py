#!/usr/bin/env python3
"""Deterministic test runner for Matilda Ears."""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import tomllib
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ENV = ROOT / ".artifacts/test/test-env"


def _test_python() -> Path:
    directory = "Scripts" if os.name == "nt" else "bin"
    executable = "python.exe" if os.name == "nt" else "python"
    return TEST_ENV / directory / executable


def _version() -> str:
    try:
        with (ROOT / "pyproject.toml").open("rb") as file:
            return str(tomllib.load(file)["project"]["version"])
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "unknown"


def _environment_ready(python: Path) -> bool:
    if not python.exists():
        return False
    probe = "import matilda_ears,matilda_transport,pytest,pytest_cov,xdist,yaml"
    return (
        subprocess.run(
            [str(python), "-c", probe],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def _ensure_test_environment() -> None:
    if os.environ.get("MATILDA_EARS_TEST_ENV") == "1":
        return

    python = _test_python()
    if not _environment_ready(python):
        if TEST_ENV.exists() and not python.exists():
            venv.EnvBuilder(with_pip=True, clear=True).create(TEST_ENV)
        elif not TEST_ENV.exists():
            venv.EnvBuilder(with_pip=True).create(TEST_ENV)

        environment = {**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
        transport = ROOT.parent / "matilda-transport"
        if transport.is_dir():
            subprocess.run(
                [str(python), "-m", "pip", "install", "-q", "-e", str(transport)],
                env=environment,
                check=True,
            )
        subprocess.run(
            [str(python), "-m", "pip", "install", "-q", "-e", f"{ROOT}[dev]"],
            env=environment,
            check=True,
        )

    environment = {**os.environ, "MATILDA_EARS_TEST_ENV": "1"}
    os.execve(python, [str(python), *sys.argv], environment)  # noqa: S606


def _examples() -> str:
    return """
🧪 MATILDA EARS TEST RUNNER

  ./scripts/test.py                         Run all tests with regression tracking
  ./scripts/test.py tests/unit              Run a test area
  ./scripts/test.py --sequential            Disable parallel execution
  ./scripts/test.py --parallel 4            Use four workers
  ./scripts/test.py --summary               Show a compact YAML failure summary
  ./scripts/test.py --coverage              Generate terminal and HTML coverage
  ./scripts/test.py --history               Show recorded runs without testing
  ./scripts/test.py --diff=-1               Compare the last two recorded runs
  ./scripts/test.py --install               Install or refresh the test environment
"""


def _run_helper(name: str, arguments: list[str]) -> int:
    return subprocess.run([sys.executable, str(ROOT / "scripts" / name), *arguments], check=False).returncode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("--sequential", action="store_true")
    parser.add_argument("--parallel", "-p", default="auto")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--test", "-t")
    parser.add_argument("--markers", "-m")
    parser.add_argument("--no-track", action="store_true")
    parser.add_argument("--force", "-f", action="store_true")
    parser.add_argument("--full-diff", action="store_true")
    parser.add_argument("--history", nargs="?", const=True)
    parser.add_argument("--diff", dest="diff_range")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--coverage", "-c", action="store_true")
    parser.add_argument("--version", action="store_true")
    return parser


def main() -> int:
    known, pytest_args = _parser().parse_known_args()
    if known.help:
        print(_examples())
        return 0
    if known.version:
        print(f"Matilda Ears Test Runner v{_version()}")
        return 0
    if known.install:
        return _run_helper("test_install.py", [])

    _ensure_test_environment()

    if known.history is not None or known.diff_range is not None:
        arguments = list(pytest_args)
        if known.history is not None:
            arguments.append("--history")
            if known.history is not True:
                arguments.append(str(known.history))
        if known.diff_range is not None:
            arguments.append("--diff")
            arguments.extend(part.strip() for part in known.diff_range.split(","))
        return _run_helper("test_history.py", arguments)

    command = [sys.executable, "-m", "pytest", *pytest_args]
    if known.test:
        command.extend(["tests", "-k", known.test])
    if known.markers:
        command.extend(["-m", known.markers])
    if known.full_diff:
        command.append("--full-diff")
    if not known.no_track and "--track-diff" not in pytest_args:
        command.append("--track-diff")

    if known.coverage:
        command.extend(["--cov=matilda_ears", "--cov-report=term-missing", "--cov-report=html"])
    if known.summary:
        command.extend(["--summary", "-q", "--tb=no"])
    elif not known.sequential and known.parallel != "off" and importlib.util.find_spec("xdist"):
        workers = known.parallel if known.parallel != "auto" else "auto"
        if not any(argument == "-n" or argument.startswith("-n") for argument in pytest_args):
            command.extend(["-n", workers])

    if known.verbose and "-v" not in pytest_args:
        command.append("-v")
    if not any(not argument.startswith("-") for argument in pytest_args) and not known.test:
        command.append("tests")

    return subprocess.run(command, check=False, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
