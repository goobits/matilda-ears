#!/usr/bin/env python3
"""Enhanced test runner for GOOBITS STT System.

Single entry point for all testing functionality: running tests, viewing history,
comparing runs, and detailed analysis.
"""

import sys
import subprocess
import argparse
import os
from pathlib import Path
import venv
import tomllib


def _test_env_python() -> Path:
    return Path(".artifacts/test/test-env/bin/python")


def _get_version() -> str:
    try:
        with open(Path(__file__).resolve().parents[1] / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        return str(data["project"]["version"])
    except Exception:
        return "unknown"


def ensure_and_use_test_env() -> None:
    """Ensure a deterministic test environment and re-exec into it.

    The monorepo runs tests in many contexts; relying on global site-packages
    leads to non-deterministic plugin sets and warning spam. This keeps Ears
    tests isolated without filtering warnings away.
    """
    if os.environ.get("MATILDA_EARS_TEST_ENV") == "1":
        return

    py = _test_env_python()
    env_dir = py.parent.parent

    def _probe_ok() -> bool:
        if not py.exists():
            return False
        probe = subprocess.run([str(py), "-c", "import pip,pytest"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return probe.returncode == 0

    if not _probe_ok():
        env_dir.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True, clear=True).create(str(env_dir))

    env = os.environ.copy()
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    # Install the test stack plus the lightweight runtime deps that are imported
    # during collection (e.g., in tests/conftest.py). Avoid heavyweight ML deps
    # (torch/torchaudio) unless a test explicitly requires them.
    transport_dir = Path(__file__).resolve().parents[2] / "matilda-transport"
    if transport_dir.is_dir():
        subprocess.run(
            [str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-e", str(transport_dir)],
            env=env,
            check=False,
        )

    reqs = [
        "pytest>=8.2.0,<10.0",
        "pytest-xdist>=3.0.0,<4.0",
        "pytest-asyncio>=1.0.0,<2.0",
        "rich>=13.0.0,<14.0",
        "rich-click>=1.7.0,<2.0",
        "numpy>=1.21.0,<3.0",
        "pydantic>=2.0.0,<3.0",
        "toml>=0.10.2,<1.0",
        "pyyaml>=6.0.1,<7.0",
        "click>=8.0.0,<9.0",
        "aiohttp>=3.8.0,<4.0",
        "websockets>=10.0,<14.0",
        "cryptography>=42.0.0,<44.0",
        "PyJWT>=2.0.0,<3.0",
        "opuslib>=3.0.0,<4.0",
    ]
    subprocess.run(
        [str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", "--upgrade", *reqs],
        env=env,
        check=False,
    )

    os.environ["MATILDA_EARS_TEST_ENV"] = "1"
    os.execv(str(py), [str(py), *sys.argv])  # noqa: S606


# Ensure deterministic test env at startup
ensure_and_use_test_env()


def show_examples():
    """Show comprehensive usage examples."""
    examples = """
🧪 MATILDA EARS TEST RUNNER

INSTALLATION:
  ./test.py --install                              # Install project with all dependencies
                                                   # (creates venv if needed, checks system deps)

BASIC USAGE:
  ./test.py                                         # Run all tests (auto-parallel + tracking)
  ./test.py tests/ears_tuner/                 # Run specific test directory
  ./test.py tests/ears_tuner/test_basic_formatting.py  # Run specific file

EXECUTION MODES:
  ./test.py --sequential                            # Force single-threaded execution
  ./test.py --parallel 4                           # Use 4 parallel workers
  ./test.py --parallel off                         # Same as --sequential

DIFF TRACKING (automatic by default):
  ./test.py tests/ears_tuner/                 # Auto-tracks changes vs last run
  ./test.py --no-track                             # Disable automatic tracking
  
VIEW RESULTS (no tests run):
  ./test.py --history                               # Show test run history
  ./test.py --diff=-1                               # Compare last run vs current
  ./test.py --diff="-5,-1"                          # Compare 5th last vs last run
  ./test.py --diff="0,10"                           # Compare first vs 10th run

FAILURE ANALYSIS:
  ./test.py --detailed                             # Parse and show expected vs actual
  ./test.py --full-diff                            # Show full assertion diffs
  ./test.py --summary                              # Show YAML summary of failures on screen

COVERAGE:
  ./test.py --coverage                             # Run tests with coverage report
  ./test.py -c tests/ears_tuner/             # Coverage for specific directory

COMMON OPTIONS:
  ./test.py --verbose                             # Verbose pytest output
  ./test.py --test test_streaming                # Test name/pattern filter
  ./test.py --markers "not slow"                 # Marker expression
  ./test.py --version                            # Show runner version

COMMON WORKFLOWS:
  ./test.py tests/ears_tuner/ --sequential --detailed
                                                   # Debug Ears Tuner issues
  ./test.py --parallel 8 tests/ears_tuner/   # Fast parallel Ears Tuner tests
  ./test.py --diff=-3                              # Check changes since 3 runs ago
  ./test.py tests/ears_tuner/ --history      # Run tests then show history

PURE PYTEST (if you prefer direct access):
  python3 -m pytest tests/ears_tuner/ --track-diff --sequential
  python3 -m pytest tests/ears_tuner/ -n 4 --detailed
  python3 -m pytest tests/ears_tuner/ --history

For more pytest options: python3 -m pytest --help
"""
    print(examples)


def _run_helper(script_name: str, args: list[str]) -> int:
    script = Path(__file__).resolve().parent / script_name
    cmd = [sys.executable, str(script), *args]
    return subprocess.run(cmd, check=False).returncode


def main():
    """Parse args and run pytest with appropriate settings."""
    # Custom help handling
    if len(sys.argv) == 2 and sys.argv[1] in ["-h", "--help"]:
        show_examples()
        return 0

    # Parse our specific args, pass everything else to pytest
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--sequential", action="store_true", help="Force sequential execution (disable parallel)")
    parser.add_argument(
        "--parallel",
        "-p",
        default="auto",
        help='Parallel workers: "auto" (7), "off" (sequential), or number like "4"',
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose pytest output")
    parser.add_argument("--test", "-t", help="Run specific test file or name pattern")
    parser.add_argument("--markers", "-m", help="Run tests matching marker expression")
    parser.add_argument("--no-track", action="store_true", help="Disable automatic diff tracking")
    parser.add_argument("--force", "-f", action="store_true", help="Reserved for CLI parity (no prompts in ears)")
    # Removed --detailed for now as it's not implemented in pytest plugins
    parser.add_argument("--full-diff", action="store_true", help="Show full assertion diffs")
    parser.add_argument(
        "--history", nargs="?", const=True, help="Show test run history. Optional: number of runs to show"
    )
    parser.add_argument("--diff", dest="diff_range", help="Compare test runs (e.g., --diff=-1 or --diff='-5,-1')")
    parser.add_argument("--install", action="store_true", help="Install the project with all dependencies")
    parser.add_argument("--summary", action="store_true", help="Show YAML summary of test failures")
    parser.add_argument("--coverage", "-c", action="store_true", help="Generate coverage report")
    parser.add_argument("--version", action="store_true", help="Show version")

    # Parse known args, keep the rest for pytest
    known_args, pytest_args = parser.parse_known_args()

    if known_args.version:
        print(f"Matilda Ears Test Runner v{_get_version()}")
        return 0

    # Handle installation in dedicated helper.
    if known_args.install:
        return _run_helper("test_install.py", [])

    # Handle read-only operations (history and diff) without running tests
    if known_args.history is not None or known_args.diff_range is not None:
        helper_args: list[str] = [*pytest_args]
        if known_args.history is not None:
            if known_args.history is True:
                helper_args.append("--history")
            else:
                helper_args.extend(["--history", str(known_args.history)])
        if known_args.diff_range is not None:
            helper_args.append("--diff")
            if "," in known_args.diff_range:
                helper_args.extend([part.strip() for part in known_args.diff_range.split(",")])
            else:
                helper_args.append(known_args.diff_range)
        return _run_helper("test_history.py", helper_args)

    # Regular test execution
    # Check if test environment exists and use it
    test_env_python = os.path.join(".artifacts/test", "test-env", "bin", "python")
    if os.path.exists(test_env_python):
        python_cmd = test_env_python
    else:
        python_cmd = "python3"

    cmd = [python_cmd, "-m", "pytest"] + pytest_args

    if known_args.test:
        cmd.extend(["tests/", "-k", known_args.test])
    if known_args.markers:
        cmd.extend(["-m", known_args.markers])

    # Handle summary mode - force sequential for proper plugin support
    if known_args.summary:
        print("🚀 Running tests in sequential mode (required for summary)...")
    elif not known_args.sequential and known_args.parallel != "off":
        import importlib.util

        if importlib.util.find_spec("xdist") is not None:
            workers = known_args.parallel if known_args.parallel != "auto" else "7"

            # Only add if not already specified
            if not any(arg.startswith("-n") for arg in pytest_args):
                cmd.extend(["-n", workers])
                print(f"🚀 Running tests in parallel with {workers} workers...")
        else:
            print("⚠️  pytest-xdist not installed. Install with: pip install pytest-xdist")
            print("Falling back to sequential execution...")
    else:
        print("🚀 Running tests in sequential mode...")

    # Add automatic diff tracking unless disabled (including for summary mode)
    if not known_args.no_track and "--track-diff" not in pytest_args:
        cmd.append("--track-diff")

    # Detailed analysis removed for now (not implemented in pytest plugins)

    # Add full diff if requested
    if known_args.full_diff and "--full-diff" not in pytest_args:
        cmd.append("--full-diff")

    # Add coverage if requested
    if known_args.coverage:
        cmd.extend(["--cov=matilda_ears", "--cov-report=term-missing", "--cov-report=html:.temp/htmlcov"])
        print("📊 Coverage report will be generated in .temp/htmlcov/")

    # Handle summary mode specially
    if known_args.summary:
        # Run pytest with summary but capture all output
        cmd.append("--summary")
        cmd.extend(["-q", "--tb=no"])

        # Try using rich for better terminal management
        try:
            from rich.live import Live
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text

            console = Console()

            # Start the process
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True
            )

            recent_lines = []
            max_recent_lines = 5
            output_lines = []

            def create_progress_panel():
                if not recent_lines:
                    return Panel("🧪 Running tests...", title="Test Progress")

                content = Text()
                for line in recent_lines[-max_recent_lines:]:
                    content.append(line + "\n")

                return Panel(content, title="Test Progress")

            # Use rich Live display
            with Live(create_progress_panel(), console=console, refresh_per_second=4) as live:
                while True:
                    line = process.stdout.readline()
                    if line == "" and process.poll() is not None:
                        break
                    if line:
                        output_lines.append(line)
                        line_clean = line.strip()

                        # Skip empty lines and certain noise
                        if line_clean and not line_clean.startswith("=") and "warnings summary" not in line_clean:
                            recent_lines.append(line_clean)
                            if len(recent_lines) > max_recent_lines:
                                recent_lines.pop(0)

                            # Update the live display
                            live.update(create_progress_panel())

            # Wait for completion and ensure Live display is completely cleared
            process.wait()

            # Move cursor up to clear the Live display area manually
            import time

            time.sleep(0.1)  # Give Rich time to finish

            # Calculate lines to clear (box height + border)
            lines_to_clear = max_recent_lines + 3  # Content + top/bottom borders + title

            # Move cursor up and clear
            for _ in range(lines_to_clear):
                print("\033[1A\033[K", end="")  # Move up one line and clear it

        except ImportError:
            # Fallback to simple mode if rich not available
            print("🧪 Running tests with summary mode...")
            print("Running tests... (progress display requires 'rich' library)")

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            output_lines = []
            for line in process.stdout:
                output_lines.append(line)
            process.wait()

        # Get full output
        output = "".join(output_lines)

        # Check for collection errors or other critical issues first
        if "ERROR" in output and ("Interrupted" in output or "error during collection" in output):
            print("❌ Test Collection Error")
            print("=" * 60)
            # Extract and show the error details
            error_start = output.find("ERRORS")
            if error_start != -1:
                error_section = output[error_start:]
                # Stop at the next major section
                for stop_marker in ["short test summary", "==========", "!!!!!!"]:
                    if stop_marker in error_section:
                        error_section = error_section[: error_section.find(stop_marker)]
                        break
                print(error_section.strip())
            return process.returncode

        # Find and display the YAML summary
        yaml_start = output.find("TEST FAILURE SUMMARY")
        if yaml_start != -1:
            # Find the start of the actual YAML (after the header)
            yaml_content_start = output.find("test_failure_summary:", yaml_start)
            if yaml_content_start != -1:
                # Print just the YAML part
                yaml_section = output[yaml_content_start:]
                # Stop at the next major section or end
                for stop_marker in ["\n\n\n", "warnings summary", "short test summary"]:
                    if stop_marker in yaml_section:
                        yaml_section = yaml_section[: yaml_section.find(stop_marker)]
                        break

                print("🎯 Test Results Summary")
                print("=" * 60)
                print(yaml_section.strip())
            else:
                print("📊 Final Results: All tests completed")
        else:
            # If no failures, show a simple completion message
            print("📊 Tests completed - checking for failures...")

        return process.returncode
    # Always use at least -v for better output unless user specified verbosity
    elif known_args.verbose:
        cmd.append("-v")
    elif not any(arg.startswith("-v") or arg in ["-q", "--quiet"] for arg in pytest_args):
        cmd.append("-v")

    # Default to tests/ if no test paths specified
    if not any(arg.startswith("tests/") or arg.endswith(".py") for arg in pytest_args) and not known_args.test:
        # Check if we have any non-flag arguments
        non_flag_args = [arg for arg in pytest_args if not arg.startswith("-")]
        if not non_flag_args:
            cmd.append("tests/")

    # Run pytest
    result = subprocess.run(cmd, check=False)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
