"""Small pytest regression-history plugin used by ``scripts/test.py``."""

from __future__ import annotations

import datetime as dt
import glob
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

HISTORY_DIR = Path(".artifacts/test")


def pytest_addoption(parser):
    group = parser.getgroup("test-diff-tracker")
    group.addoption("--track-diff", action="store_true", help="Record this run and compare it with the last run")
    group.addoption("--history", nargs="?", const=10, type=int, metavar="N", help="Show the last N recorded runs")
    group.addoption("--diff", dest="diff_range", nargs="*", metavar="INDEX", help="Compare recorded runs")


def pytest_configure(config):
    if config.getoption("--track-diff") or config.getoption("--history") is not None or config.getoption("diff_range"):
        config.pluginmanager.register(DiffTracker(config), "difftracker")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--history") is not None or config.getoption("diff_range"):
        items.clear()


class DiffTracker:
    def __init__(self, config):
        self.config = config
        self.results: dict[str, dict[str, Any]] = {}
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _test_path(session) -> str:
        paths = session.config.getoption("file_or_dir") or ["tests"]
        for raw_path in paths:
            path = Path(raw_path)
            parts = path.parts
            if "tests" in parts:
                index = parts.index("tests")
                return "/".join(parts[index : index + 2]) if len(parts) > index + 1 else "tests"
        return "tests"

    @staticmethod
    def _history_file(test_path: str) -> Path:
        if test_path == "tests":
            name = "full"
        elif test_path.startswith("tests/"):
            name = test_path.removeprefix("tests/").replace("/", "_")
        else:
            name = hashlib.md5(test_path.encode(), usedforsecurity=False).hexdigest()[:8]
        return HISTORY_DIR / f"test_history_{name}.json"

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"runs": [], "test_metadata": {}}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"runs": [], "test_metadata": {}}
        data.setdefault("runs", [])
        data.setdefault("test_metadata", {})
        return data

    @staticmethod
    def _save(history: dict[str, Any], path: Path) -> None:
        history["runs"] = history["runs"][-50:]
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(history, separators=(",", ":")), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _short_name(nodeid: str) -> str:
        parts = nodeid.split("::")
        return "::".join(parts[-2:]) if len(parts) >= 3 else parts[-1]

    @staticmethod
    def _failure_details(report) -> dict[str, str]:
        if not getattr(report, "longrepr", None):
            return {}
        expected = actual = None
        for line in str(report.longrepr).splitlines():
            if "E     - " in line:
                expected = line.split("E     - ", 1)[1].strip()
            elif "E     + " in line:
                actual = line.split("E     + ", 1)[1].strip()
        return {"expected": expected, "actual": actual} if expected and actual else {}

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            status = "PASSED" if report.passed else "FAILED" if report.failed else "SKIPPED"
            result: dict[str, Any] = {"status": status, "full_path": report.nodeid}
            if details := self._failure_details(report):
                result["failure_details"] = details
            self.results[self._short_name(report.nodeid)] = result
        yield

    def _run_record(self, test_path: str) -> dict[str, Any]:
        counts = {
            status: sum(item["status"] == status for item in self.results.values())
            for status in ("PASSED", "FAILED", "SKIPPED")
        }
        return {
            "timestamp": dt.datetime.now().isoformat(),
            "test_path": test_path,
            "summary": {
                "total": len(self.results),
                "passed": counts["PASSED"],
                "failed": counts["FAILED"],
                "skipped": counts["SKIPPED"],
            },
            "tests": self.results,
            "return_code": int(bool(counts["FAILED"])),
        }

    @staticmethod
    def _diff(history: dict[str, Any], first: int, second: int) -> dict[str, Any]:
        if len(history["runs"]) < 2:
            raise IndexError("Not enough runs to compare")
        before, after = history["runs"][first], history["runs"][second]
        before_tests, after_tests = before["tests"], after["tests"]
        shared = before_tests.keys() & after_tests.keys()
        return {
            "newly_passing": sorted(
                name
                for name in shared
                if before_tests[name]["status"] == "FAILED" and after_tests[name]["status"] == "PASSED"
            ),
            "newly_failing": sorted(
                name
                for name in shared
                if before_tests[name]["status"] == "PASSED" and after_tests[name]["status"] == "FAILED"
            ),
            "still_failing": sorted(
                name for name in shared if before_tests[name]["status"] == after_tests[name]["status"] == "FAILED"
            ),
            "new_tests": sorted(after_tests.keys() - before_tests.keys()),
            "removed_tests": sorted(before_tests.keys() - after_tests.keys()),
        }

    @staticmethod
    def _print_diff(diff: dict[str, Any]) -> None:
        fixed = len(diff["newly_passing"])
        broken = len(diff["newly_failing"])
        score = fixed - broken
        prefix = "+" if score > 0 else ""
        symbol = "✅" if score >= 0 else "❌"
        print(f"\n{symbol} Regression Score: {prefix}{score} ({fixed} fixed, {broken} broke)")
        print("=" * 70)
        for title, key, marker in (
            ("NEWLY FAILING (Regressions)", "newly_failing", "-"),
            ("NEWLY PASSING (Fixes)", "newly_passing", "+"),
        ):
            if diff[key]:
                print(f"\n{title}:")
                for name in diff[key]:
                    print(f"{marker} {name}")
        if diff["new_tests"] or diff["removed_tests"]:
            print(f"\n{len(diff['new_tests'])} new | {len(diff['removed_tests'])} removed")
        if diff["still_failing"]:
            print(f"\n({len(diff['still_failing'])} tests are still failing)")

    @staticmethod
    def _print_history(history: dict[str, Any], limit: int) -> None:
        runs = history["runs"]
        if not runs:
            print("No test runs recorded yet.")
            return
        print("\n📜 TEST RUN HISTORY")
        print("=" * 60)
        start = max(0, len(runs) - limit)
        for index, run in enumerate(runs[start:], start=start):
            timestamp = run["timestamp"][:16].replace("T", " ")
            summary = run["summary"]
            current = " (current)" if index == len(runs) - 1 else ""
            print(f"[{index}] {timestamp}: {summary['passed']}/{summary['total']} passing{current}")

    @staticmethod
    def _indices(values: list[str]) -> tuple[int, int]:
        if len(values) == 1:
            index = int(values[0])
            return (-2, -1) if index == -1 else (index, -1)
        if len(values) == 2:
            return int(values[0]), int(values[1])
        raise ValueError("Expected one or two run indices")

    def pytest_sessionfinish(self, session) -> None:
        if hasattr(self.config, "workerinput"):
            worker_id = self.config.workerinput["workerid"]
            (HISTORY_DIR / f"partial_results_{worker_id}.json").write_text(json.dumps(self.results), encoding="utf-8")
            return

        partial_files = glob.glob(str(HISTORY_DIR / "partial_results_*.json"))
        for filename in partial_files:
            path = Path(filename)
            self.results.update(json.loads(path.read_text(encoding="utf-8")))
            path.unlink()

        test_path = self._test_path(session)
        history_file = self._history_file(test_path)
        history = self._load(history_file)

        if self.config.getoption("--track-diff"):
            if not self.results:
                print("\n⚠️ No test results were collected. Skipping diff tracking.")
                return
            history["runs"].append(self._run_record(test_path))
            self._save(history, history_file)
            if len(history["runs"]) == 1:
                print("\n📊 First run recorded. No diff to show.")
            else:
                self._print_diff(self._diff(history, -2, -1))
            return

        if self.config.getoption("--history") is not None:
            self._print_history(history, self.config.getoption("--history"))
            session.exitstatus = pytest.ExitCode.OK
            return

        if values := self.config.getoption("diff_range"):
            try:
                self._print_diff(self._diff(history, *self._indices(values)))
            except (IndexError, ValueError) as error:
                print(f"\n❌ Unable to compare runs: {error}")
            session.exitstatus = pytest.ExitCode.OK
