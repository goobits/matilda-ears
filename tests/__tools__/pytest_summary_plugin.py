"""Simplified pytest plugin for clean failure summaries.
Generates YAML/JSON reports with proper value extraction.
"""

import pytest
import yaml
import re
from collections import defaultdict
from datetime import datetime


def extract_failure_details(longrepr: str) -> dict:
    """Extract failure details from pytest output."""
    # Look for the actual assertion line with real values
    match = re.search(r"AssertionError: Input '([^']+)' should.*?'([^']+)'.*?got '([^']+)'", longrepr)
    if match:
        return {"input": match.group(1), "expected": match.group(2), "actual": match.group(3)}

    # Try other patterns
    match = re.search(r"assert '([^']+)' == '([^']+)'", longrepr)
    if match:
        return {"input": "Unknown", "expected": match.group(2), "actual": match.group(1)}

    return None


def categorize_failure(test_name: str, input_text: str, expected: str, actual: str) -> tuple:
    """Categorize the failure type."""
    issues = []

    # Punctuation
    if expected.endswith((".", "!", "?")) and not actual.endswith((".", "!", "?")):
        issues.append("missing_punctuation")

    # Capitalization
    if expected and actual and expected[0] != actual[0]:
        if expected[0].isupper() and actual[0].islower():
            issues.append("missing_capital")
        elif expected[0].islower() and actual[0].isupper():
            issues.append("extra_capital")

    # Specific patterns
    if "README.md" in expected and "README.Md" in actual:
        issues.append("readme_case")
    if "@" in expected and " at " in actual:
        issues.append("email_at_symbol")
    if ":" in expected and " colon " in actual:
        issues.append("colon_word")
    if "/" in expected and " slash " in actual:
        issues.append("slash_word")
    if "_" in expected and " underscore " in actual:
        issues.append("underscore_word")

    # Numbers
    if re.search(r"\d", expected) and not re.search(r"\d", actual):
        if any(word in input_text.lower() for word in ["one", "two", "three", "four", "five"]):
            issues.append("number_words")

    # Currency
    if "$" in expected and ("dollars" in actual or "cents" in actual):
        issues.append("currency_format")

    # Time
    if re.search(r"\d\s*(AM|PM)", expected) and not re.search(r"\d\s*(AM|PM)", actual):
        issues.append("time_format")

    # Category from test name
    if "web" in test_name or "email" in test_name:
        category = "web_entities"
    elif "code" in test_name or "filename" in test_name:
        category = "code_entities"
    elif "numeric" in test_name or "number" in test_name:
        category = "numeric_entities"
    elif "time" in test_name or "date" in test_name:
        category = "temporal_entities"
    elif "financial" in test_name or "currency" in test_name:
        category = "financial_entities"
    elif "math" in test_name:
        category = "math_entities"
    else:
        category = "text_formatting"

    return category, issues or ["other"]


class SummaryReporter:
    def __init__(self):
        self.failures = []
        self.passed = 0
        self.total = 0

    def add_result(self, nodeid, passed, failure_details=None):
        self.total += 1
        if passed:
            self.passed += 1
        elif failure_details:
            test_name = nodeid.split("::")[-1]
            module = nodeid.split("::")[0].replace("tests/text_formatting/", "")

            category, issues = categorize_failure(
                test_name,
                failure_details.get("input", ""),
                failure_details.get("expected", ""),
                failure_details.get("actual", ""),
            )

            self.failures.append(
                {"test": test_name, "module": module, "category": category, "issues": issues, **failure_details}
            )

    def generate_yaml(self):
        """Generate YAML report."""
        # Group by issue pattern
        issue_groups = defaultdict(list)

        for failure in self.failures:
            issue_key = tuple(sorted(failure["issues"]))
            issue_groups[issue_key].append(failure)

        # Build report
        report = {
            "test_failure_summary": {
                "statistics": {
                    "total": self.total,
                    "passed": self.passed,
                    "failed": len(self.failures),
                    "unique_issues": len(issue_groups),
                    "timestamp": datetime.now().isoformat(),
                },
                "issues": [],
            }
        }

        # Sort by frequency
        for issues, failures in sorted(issue_groups.items(), key=lambda x: -len(x[1])):
            issue_name = " + ".join(issues)

            # Group by category
            by_category = defaultdict(list)
            for f in failures:
                by_category[f["category"]].append(f)

            issue_data = {
                "type": issue_name,
                "count": len(failures),
                "categories": list(by_category.keys()),
                "examples": [],
            }

            # Add up to 3 examples
            for f in failures[:3]:
                issue_data["examples"].append(
                    {"test": f["test"], "input": f["input"], "expected": f["expected"], "actual": f["actual"]}
                )

            if len(failures) > 3:
                issue_data["more_tests"] = [f["test"] for f in failures[3:6]]
                if len(failures) > 6:
                    issue_data["total_affected"] = len(failures)

            report["test_failure_summary"]["issues"].append(issue_data)

        return report


# Plugin globals
_reporter = None


def pytest_addoption(parser):
    """Add options."""
    parser.addoption("--summary", action="store_true", help="Show YAML failure summary")


def pytest_configure(config):
    """Initialize reporter if needed."""
    global _reporter
    if config.getoption("--summary"):
        _reporter = SummaryReporter()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture test results."""
    global _reporter
    if not _reporter:
        yield
        return

    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        passed = report.outcome == "passed"
        failure_details = None

        if not passed and hasattr(report, "longrepr"):
            failure_details = extract_failure_details(str(report.longrepr))

        _reporter.add_result(item.nodeid, passed, failure_details)


def pytest_sessionfinish(session, exitstatus):
    """Generate report."""
    global _reporter
    if not _reporter or not _reporter.failures:
        return

    report = _reporter.generate_yaml()

    # Print YAML directly to console
    print("\n" + "=" * 80)
    print("TEST FAILURE SUMMARY")
    print("=" * 80)

    yaml_output = yaml.dump(report, default_flow_style=False, sort_keys=False, width=120, indent=2, allow_unicode=True)
    print(yaml_output)
