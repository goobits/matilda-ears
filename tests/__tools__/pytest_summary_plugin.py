"""Pytest plugin that emits a compact YAML failure summary."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any

import pytest
import yaml


def _failure_details(longrepr: str) -> dict[str, str]:
    patterns = (
        r"AssertionError: Input '([^']+)' should.*?'([^']+)'.*?got '([^']+)'",
        r"assert '([^']+)' == '([^']+)'",
    )
    for pattern in patterns:
        if match := re.search(pattern, longrepr, re.DOTALL):
            actual, expected = match.group(1), match.group(2)
            return {
                "input": match.group(1) if len(match.groups()) == 3 else "Unknown",
                "expected": expected,
                "actual": match.group(3) if len(match.groups()) == 3 else actual,
            }
    return {}


class SummaryReporter:
    def __init__(self) -> None:
        self.total = 0
        self.passed = 0
        self.skipped = 0
        self.failures: list[dict[str, Any]] = []

    def add(self, report) -> None:
        self.total += 1
        if report.passed:
            self.passed += 1
            return
        if report.skipped:
            self.skipped += 1
            return
        details = _failure_details(str(report.longrepr))
        self.failures.append({"test": report.nodeid, **details})

    def report(self) -> dict[str, Any]:
        grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for failure in self.failures:
            grouped["assertion" if "expected" in failure else "test_error"].append(failure)
        return {
            "test_failure_summary": {
                "statistics": {
                    "total": self.total,
                    "passed": self.passed,
                    "skipped": self.skipped,
                    "failed": len(self.failures),
                    "unique_issues": len(grouped),
                    "timestamp": datetime.now().isoformat(),
                },
                "issues": [
                    {"type": issue, "count": len(failures), "examples": failures[:3]}
                    for issue, failures in grouped.items()
                ],
            }
        }


def pytest_addoption(parser) -> None:
    parser.addoption("--summary", action="store_true", help="Show a YAML failure summary")


def pytest_configure(config) -> None:
    if config.getoption("--summary"):
        config._ears_summary = SummaryReporter()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    reporter = getattr(item.config, "_ears_summary", None)
    if reporter and report.when == "call":
        reporter.add(report)


def pytest_sessionfinish(session, exitstatus) -> None:
    reporter = getattr(session.config, "_ears_summary", None)
    if not reporter or not reporter.failures:
        return
    print("\n" + "=" * 80)
    print("TEST FAILURE SUMMARY")
    print("=" * 80)
    print(yaml.safe_dump(reporter.report(), sort_keys=False, width=120, allow_unicode=True))
