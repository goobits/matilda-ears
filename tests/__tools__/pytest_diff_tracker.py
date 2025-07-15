# tests/pytest_diff_tracker.py

import pytest
import json
import datetime
from pathlib import Path
from typing import Dict
import os
import glob
import hashlib
from functools import lru_cache
import sys

# --- Constants ---
HISTORY_DIR = Path(".test_artifacts")

# --- Pytest Hooks ---


def pytest_addoption(parser):
    """Add options to pytest command line."""
    group = parser.getgroup("test-diff-tracker")
    group.addoption("--track-diff", action="store_true", default=False, help="Run tests and show diff vs last run.")
    group.addoption("--history", nargs="?", const=10, type=int, metavar="N",
                   help="Show test run history. Optional N specifies number of runs to show (default: 10).")
    group.addoption(
        "--diff",
        dest="diff_range",
        nargs="*",
        metavar="INDICES",
        default=None,
        help="Compare runs. Examples: '--diff -1' (last vs current), '--diff -5 -1' (5th last vs last), '--diff 0 5' (first vs 5th)",
    )


def pytest_configure(config):
    """Called after command line options are parsed."""
    # If any of our options are used, register the plugin
    if config.getoption("--track-diff") or config.getoption("--history") is not None or config.getoption("diff_range"):
        plugin = DiffTracker(config)
        config.pluginmanager.register(plugin, "difftracker")


def pytest_collection_modifyitems(config, items):
    """Modify collection to skip tests for read-only operations."""
    # If we're only showing history or diff, don't run any tests
    if config.getoption("--history") is not None or config.getoption("diff_range"):
        # Clear all collected items to prevent test execution
        items.clear()


# --- Plugin Class ---


class DiffTracker:
    def __init__(self, config):
        self.config = config
        self.current_run_results = {}
        self.test_path = None
        self.history_file = None
        HISTORY_DIR.mkdir(exist_ok=True)

    @lru_cache(maxsize=32)
    def _normalize_test_path(self, test_args: tuple) -> str:
        """Convert test arguments to normalized path string."""
        args_str = " ".join(test_args).strip()

        # Handle common patterns
        if args_str.startswith("tests/text_formatting"):
            return "tests/text_formatting"
        if args_str.startswith("tests/infrastructure"):
            return "tests/infrastructure"
        if args_str.startswith("tests/pipeline"):
            return "tests/pipeline"
        if args_str.startswith("tests/networking"):
            return "tests/networking"
        if args_str == "tests" or args_str == "tests/":
            return "tests"

        # For complex paths, use first directory component
        if args_str.startswith("tests/"):
            parts = args_str.split("/")
            if len(parts) >= 2:
                return f"tests/{parts[1]}"

        return "tests"

    def _get_history_file(self, test_path: str) -> Path:
        """Get history file for specific test path."""
        path_map = {
            "tests/text_formatting": "text_formatting",
            "tests/infrastructure": "infrastructure",
            "tests/pipeline": "pipeline",
            "tests/networking": "networking",
            "tests": "full",
        }

        normalized = path_map.get(test_path)
        if not normalized:
            normalized = hashlib.md5(test_path.encode()).hexdigest()[:8]

        return HISTORY_DIR / f"test_history_{normalized}.json"

    def _detect_test_path(self, session) -> str:
        """Robustly detect test path using pytest's internal configuration."""
        test_paths = session.config.getoption("file_or_dir")
        if not test_paths:
            # If no paths specified, pytest defaults to current directory
            test_paths = [os.getcwd()]

        # Convert paths to relative to workspace and normalize
        test_args = []
        for path in test_paths:
            abs_path = os.path.abspath(path)
            # Try to make it relative to the workspace
            try:
                rel_path = os.path.relpath(abs_path, os.getcwd())
                if rel_path.startswith("tests/") or rel_path == "tests":
                    test_args.append(rel_path)
                elif abs_path.endswith("/tests") or "/tests/" in abs_path:
                    # Extract tests part from absolute path
                    if "/tests/" in abs_path:
                        tests_part = "tests/" + abs_path.split("/tests/", 1)[1]
                    else:
                        tests_part = "tests"
                    test_args.append(tests_part)
                else:
                    test_args.append("tests")  # Default fallback
            except ValueError:
                # If we can't make it relative, default to 'tests'
                test_args.append("tests")

        return self._normalize_test_path(tuple(test_args))

    def _load_history(self, history_file: Path) -> Dict:
        """Load test history from file."""
        if not history_file.exists():
            return {"runs": [], "test_metadata": {}}

        try:
            import ujson

            with open(history_file, "rb") as f:
                return ujson.load(f)
        except ImportError:
            with open(history_file) as f:
                return json.load(f)

    def _save_history(self, history: Dict, history_file: Path):
        """Save test history to file."""
        if len(history["runs"]) > 50:
            history["runs"] = history["runs"][-50:]

        temp_file = history_file.with_suffix(".tmp")
        with open(temp_file, "w") as f:
            json.dump(history, f, separators=(",", ":"))
        temp_file.replace(history_file)

    def _simplify_nodeid(self, nodeid: str) -> str:
        """Convert pytest nodeid to simplified test name matching old format."""
        # Example: 'tests/text_formatting/test_capitalization.py::TestCapitalization::test_sentence_case'
        # Should become: 'TestCapitalization::test_sentence_case'

        parts = nodeid.split("::")
        if len(parts) >= 2:
            # Get the class and method parts
            if len(parts) >= 3:
                # Class::method format
                return f"{parts[-2]}::{parts[-1]}"
            # Just method format
            return parts[-1]
        # Fallback: just return the nodeid as is
        return nodeid

    def _parse_failure_details(self, report) -> Dict:
        """Extract failure details from test report."""
        failure_details = {}

        if hasattr(report, "longrepr") and report.longrepr:
            repr_str = str(report.longrepr)

            # Look for assertion errors with expected vs actual
            if "AssertionError" in repr_str:
                lines = repr_str.split("\n")
                expected = None
                actual = None

                for line in lines:
                    if "E     - " in line:
                        expected = line.split("E     - ", 1)[1].strip()
                    elif "E     + " in line:
                        actual = line.split("E     + ", 1)[1].strip()
                        if expected and actual:
                            failure_details = {"expected": expected, "actual": actual}
                            break

        return failure_details

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_logreport(self, report):
        """Capture result of each test."""
        # This hook is called for setup, call, and teardown.
        # We only care about the 'call' phase for pass/fail status.
        if report.when == "call":
            # Get the simplified test name
            short_name = self._simplify_nodeid(report.nodeid)

            # Determine status
            if report.passed:
                status = "PASSED"
            elif report.failed:
                status = "FAILED"
            elif report.skipped:
                status = "SKIPPED"
            else:
                status = "UNKNOWN"

            # Store the result
            result = {"status": status, "full_path": report.nodeid}

            # Add failure details if test failed
            if status == "FAILED":
                failure_details = self._parse_failure_details(report)
                if failure_details:
                    result["failure_details"] = failure_details

            self.current_run_results[short_name] = result

        yield  # Allows other plugins to process the report

    def _create_run_record(self, test_path: str = "tests/") -> Dict:
        """Create a run record compatible with the old format."""
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "test_path": test_path,
            "summary": {
                "total": len(self.current_run_results),
                "passed": sum(1 for r in self.current_run_results.values() if r["status"] == "PASSED"),
                "failed": sum(1 for r in self.current_run_results.values() if r["status"] == "FAILED"),
                "skipped": sum(1 for r in self.current_run_results.values() if r["status"] == "SKIPPED"),
            },
            "tests": self.current_run_results,
            "return_code": 0 if all(r["status"] != "FAILED" for r in self.current_run_results.values()) else 1,
        }

    def _get_diff(self, history: Dict, run1_idx: int = -2, run2_idx: int = -1) -> Dict:
        """Generate diff between two test runs."""
        if len(history["runs"]) < 2:
            return {"error": "Not enough runs to compare"}

        run1 = history["runs"][run1_idx]
        run2 = history["runs"][run2_idx]

        tests1 = run1["tests"]
        tests2 = run2["tests"]

        all_tests = set(tests1.keys()) | set(tests2.keys())

        diff = {
            "run1_timestamp": run1["timestamp"],
            "run2_timestamp": run2["timestamp"],
            "newly_passing": [],
            "newly_failing": [],
            "still_failing": [],
            "still_passing": [],
            "new_tests": [],
            "removed_tests": [],
            "summary": {
                "total_change": len(tests2) - len(tests1),
                "passed_change": run2["summary"]["passed"] - run1["summary"]["passed"],
                "failed_change": run2["summary"]["failed"] - run1["summary"]["failed"],
            },
        }

        for test in all_tests:
            if test not in tests1:
                diff["new_tests"].append(test)
            elif test not in tests2:
                diff["removed_tests"].append(test)
            else:
                status1 = tests1[test]["status"]
                status2 = tests2[test]["status"]

                if status1 == "FAILED" and status2 == "PASSED":
                    diff["newly_passing"].append(test)
                elif status1 == "PASSED" and status2 == "FAILED":
                    diff["newly_failing"].append({"name": test, "details": tests2[test].get("failure_details", {})})
                elif status1 == "FAILED" and status2 == "FAILED":
                    diff["still_failing"].append({"name": test, "details": tests2[test].get("failure_details", {})})
                elif status1 == "PASSED" and status2 == "PASSED":
                    diff["still_passing"].append(test)

        return diff

    def _print_diff(self, diff: Dict, run_summary: Dict, session=None):
        """Print a human-readable diff focusing on regressions."""
        if "error" in diff:
            self._write_line(f"\n❌ {diff['error']}", session)
            return

        # --- Calculate the Regression Score ---
        newly_failing_count = len(diff["newly_failing"])
        newly_passing_count = len(diff["newly_passing"])
        regression_score = newly_passing_count - newly_failing_count

        # --- Print the Summary Header ---
        summary_parts = []
        if regression_score > 0:
            score_color = "✅"
            summary_parts.append(f"[bold green]Regression Score: +{regression_score}[/bold green]")
        elif regression_score < 0:
            score_color = "❌"
            summary_parts.append(f"[bold red]Regression Score: {regression_score}[/bold red]")
        else:
            score_color = "✅"
            summary_parts.append("[bold]Regression Score: 0[/bold]")

        summary_parts.append(f"({newly_passing_count} fixed, {newly_failing_count} broke)")

        # Also report on new/removed tests, which don't affect the score.
        new_tests_count = len(diff.get("new_tests", []))
        removed_tests_count = len(diff.get("removed_tests", []))
        if new_tests_count > 0:
            summary_parts.append(f"| {new_tests_count} new")
        if removed_tests_count > 0:
            summary_parts.append(f"| {removed_tests_count} removed")

        self._write_line(f"\n{score_color} {' '.join(summary_parts)}", session)
        self._write_line("=" * 70, session)

        # --- Print Detailed Changes ---
        if diff["newly_failing"]:
            self._write_line("\n[bold red]NEWLY FAILING (Regressions):[/bold red]", session)
            for test in diff["newly_failing"]:
                self._write_line(f"- {test['name']}", session)
                if test["details"]:
                    self._write_line(
                        f"  [yellow]Expected:[/yellow] \"{test['details'].get('expected', 'N/A')}\"", session
                    )
                    self._write_line(
                        f"  [yellow]Actual:[/yellow]   \"{test['details'].get('actual', 'N/A')}\"", session
                    )

        if diff["newly_passing"]:
            self._write_line("\n[bold green]NEWLY PASSING (Fixes):[/bold green]", session)
            for test in diff["newly_passing"]:
                self._write_line(f"+ {test}", session)

        if diff.get("new_tests"):
            failing_new_tests = [
                t for t in diff["new_tests"] if self.current_run_results.get(t, {}).get("status") == "FAILED"
            ]
            if failing_new_tests:
                self._write_line("\n[bold yellow]NEW TESTS (Currently Failing):[/bold yellow]", session)
                for test_name in failing_new_tests:
                    self._write_line(f"• {test_name}", session)

        still_failing_count = len(diff["still_failing"])
        if still_failing_count > 0:
            self._write_line(f"\n[dim]({still_failing_count} tests are still failing)[/dim]", session)

    def _print_history(self, history: Dict, limit: int = 10):
        """Print test run history in the proposal format."""
        if not history["runs"]:
            print("No test runs recorded yet.")
            return

        print("\n📜 TEST RUN HISTORY")
        print("=" * 60)

        runs_to_show = history["runs"][-limit:]
        for i, run in enumerate(runs_to_show):
            # Calculate index from end
            actual_idx = len(history["runs"]) - limit + i
            if actual_idx < 0:
                actual_idx = i

            timestamp = run["timestamp"][:16].replace("T", " ")  # Format: 2025-01-07 10:15
            passed = run["summary"]["passed"]
            total = run["summary"]["total"]

            status = "(current)" if i == len(runs_to_show) - 1 else ""
            print(f"[{actual_idx}] {timestamp}: {passed}/{total} passing {status}")

    def _write_line(self, text: str, session=None):
        """Write line to terminal, using session if available."""
        print(text, file=sys.stdout, flush=True)

    def _parse_diff_range(self, diff_range: list) -> tuple:
        """Parse diff range list into (from_idx, to_idx).

        Examples:
          ['-1'] -> compare second to last vs last run
          ['-5', '-1'] -> compare 5th last vs last
          ['0', '5'] -> compare first vs 5th
          ['-3'] -> compare 3rd last vs last run

        """
        if len(diff_range) == 1:
            # Single index means compare previous run with last run
            # e.g., -1 means compare run[-2] with run[-1]
            idx = int(diff_range[0])
            if idx == -1:
                # Special case: -1 means compare second to last with last
                from_idx = -2
                to_idx = -1
            else:
                # For other values, compare that index with the last run
                from_idx = idx
                to_idx = -1
            return from_idx, to_idx
        if len(diff_range) == 2:
            # Two indices
            from_idx = int(diff_range[0])
            to_idx = int(diff_range[1])
            return from_idx, to_idx
        raise ValueError(f"Invalid diff range: {diff_range}. Expected 1 or 2 indices.")

    def pytest_sessionfinish(self, session):
        """Called after the entire test session finishes. Handles xdist."""
        # Only run if one of our flags is active
        if not (
            self.config.getoption("--track-diff")
            or self.config.getoption("--history")
            or self.config.getoption("diff_range")
        ):
            return

        # Distinguish between xdist master and worker nodes
        # 'workerinput' is a dictionary provided by xdist to workers. It's None on the master.
        is_worker = hasattr(self.config, "workerinput")

        if is_worker:
            # --- WORKER NODE LOGIC ---
            # Each worker saves its partial results to a temporary file.
            worker_id = self.config.workerinput["workerid"]
            temp_file = HISTORY_DIR / f"partial_results_{worker_id}.json"
            with open(temp_file, "w") as f:
                json.dump(self.current_run_results, f)
            return  # Worker's job is done.

        # --- MASTER NODE / SEQUENTIAL RUN LOGIC ---
        if not is_worker:
            # Aggregate results from workers if they exist
            partial_files = glob.glob(str(HISTORY_DIR / "partial_results_*.json"))
            if partial_files:
                aggregated_results = {}
                for f in partial_files:
                    with open(f) as partial_f:
                        aggregated_results.update(json.load(partial_f))
                    os.remove(f)
                self.current_run_results = aggregated_results

            # Determine test path using pytest's internal configuration (more robust)
            self.test_path = self._detect_test_path(session)
            self.history_file = self._get_history_file(self.test_path)

            history = self._load_history(self.history_file)

            if self.config.getoption("--track-diff"):
                if not self.current_run_results:
                    self._write_line("\n⚠️ No test results were collected. Skipping diff tracking.", session)
                    return

                run_record = self._create_run_record(self.test_path)
                history["runs"].append(run_record)
                self._save_history(history, self.history_file)

                if len(history["runs"]) >= 2:
                    diff = self._get_diff(history)
                    self._print_diff(diff, run_record["summary"], session)
                else:
                    self._write_line("\n📊 First run recorded. No diff to show.", session)

            elif self.config.getoption("--history") is not None:
                # For history and diff commands, we also need to detect the test path
                if not self.test_path:
                    self.test_path = self._detect_test_path(session)
                    self.history_file = self._get_history_file(self.test_path)
                    history = self._load_history(self.history_file)
                history_limit = self.config.getoption("--history")
                if history_limit is None:
                    history_limit = 10  # Default if flag used without value
                self._print_history(history, limit=history_limit)

            elif self.config.getoption("diff_range"):
                # For history and diff commands, we also need to detect the test path
                if not self.test_path:
                    self.test_path = self._detect_test_path(session)
                    self.history_file = self._get_history_file(self.test_path)
                    history = self._load_history(self.history_file)

                diff_range = self.config.getoption("diff_range")
                try:
                    from_idx, to_idx = self._parse_diff_range(diff_range)

                    num_runs = len(history["runs"])
                    if from_idx >= 0:
                        from_idx -= num_runs
                    if to_idx >= 0:
                        to_idx -= num_runs

                    if abs(from_idx) > num_runs or abs(to_idx) > num_runs:
                        raise IndexError("Index out of range for historical runs.")

                    diff = self._get_diff(history, from_idx, to_idx)
                    if "error" not in diff:
                        target_run = history["runs"][to_idx]
                        self._print_diff(diff, target_run["summary"], session)
                    else:
                        self._write_line(f"\n❌ {diff['error']}", session)

                except (ValueError, IndexError) as e:
                    self._write_line(f"\n❌ Error with diff range '{diff_range}': {e}", session)
