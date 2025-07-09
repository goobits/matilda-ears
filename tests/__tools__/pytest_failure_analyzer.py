"""Pytest plugin for failure analysis with YAML/JSON export.
Provides clean, deduplicated summaries of test failures.
"""

import pytest
import yaml
import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple, Optional


class FailureAnalyzer:
    """Analyzes test failures and generates structured reports."""

    def __init__(self):
        self.failures = []
        self.passed = 0
        self.total = 0

    def add_result(self, nodeid: str, passed: bool, failure_info: Optional[Dict] = None):
        """Record a test result."""
        self.total += 1
        if passed:
            self.passed += 1
        elif failure_info:
            self.failures.append(
                {
                    "nodeid": nodeid,
                    "test": nodeid.split("::")[-1],
                    "module": nodeid.split("::")[0].replace("tests/text_formatting/", ""),
                    **failure_info,
                }
            )

    def extract_failure_info(self, longrepr: str) -> Optional[Dict]:
        """Extract input/expected/actual from various assertion patterns."""
        # Pattern 1: Standard "Input 'X' should format to 'Y', got 'Z'"
        # First try to extract from formatted strings with {variables}
        input_match = re.search(
            r"Input '([^']+)'", longrepr.replace("{input_text}", "").replace("'{'", "'").replace("'}'", "'")
        )
        if input_match and "{" in longrepr:
            # This is a formatted string pattern, extract the actual values
            expected_match = re.search(
                r"should (?:format to|be|protect|detect as|remain)[:\s]*'([^']+)'",
                longrepr.replace("{expected}", "").replace("'{'", "'").replace("'}'", "'"),
            )
            actual_match = re.search(
                r"got '([^']+)'",
                longrepr.replace("{result}", "").replace("{actual}", "").replace("'{'", "'").replace("'}'", "'"),
            )

            if expected_match:
                return {
                    "input": input_match.group(1),
                    "expected": expected_match.group(1),
                    "actual": actual_match.group(1) if actual_match else "N/A",
                }

        patterns = [
            (
                r"Input '([^']+)'.*?should (?:format to|be|protect|detect as|remain|format to currency notation)[:\s]*'([^']+)'(?:.*?got '([^']+)')?",
                lambda m: {"input": m.group(1), "expected": m.group(2), "actual": m.group(3) or "N/A"},
            ),
            # Pattern 2: Multiple acceptable outputs
            (
                r"Input '([^']+)'.*?should format to '([^']+)' or '([^']+)'.*?got '([^']+)'",
                lambda m: {"input": m.group(1), "expected": f"{m.group(2)} or {m.group(3)}", "actual": m.group(4)},
            ),
            # Pattern 3: Direct assertions
            (
                r"assert format_transcription\('([^']+)'\) == '([^']+)'",
                lambda m: {
                    "input": m.group(1),
                    "expected": m.group(2),
                    "actual": self._extract_actual_from_assert(longrepr),
                },
            ),
            # Pattern 4: Currency notation
            (
                r"Input '([^']+)' should format to currency notation.*?got '([^']+)'",
                lambda m: {"input": m.group(1), "expected": "currency notation", "actual": m.group(2)},
            ),
        ]

        for pattern, extractor in patterns:
            match = re.search(pattern, longrepr)
            if match:
                return extractor(match)

        # Pattern 5: pytest-clarity format
        if "assert == failed" in longrepr and "LHS vs RHS" in longrepr:
            return self._extract_from_clarity(longrepr)

        return None

    def _extract_actual_from_assert(self, longrepr: str) -> str:
        """Extract actual value from assertion error."""
        match = re.search(r"assert '([^']+)' ==", longrepr)
        return match.group(1) if match else "N/A"

    def _extract_from_clarity(self, longrepr: str) -> Optional[Dict]:
        """Extract from pytest-clarity output."""
        input_match = re.search(r"Input '([^']+)'", longrepr)
        if not input_match:
            return None

        # Look for LHS vs RHS pattern
        lhs_rhs = re.search(r"LHS vs RHS.*?\n\s*([^\n]+)\n\s*([^\n]+)", longrepr, re.DOTALL)
        if lhs_rhs:
            return {
                "input": input_match.group(1),
                "expected": lhs_rhs.group(2).strip(),
                "actual": lhs_rhs.group(1).strip(),
            }
        return None

    def categorize_issue(self, failure: Dict) -> Tuple[str, List[str]]:
        """Categorize the failure by issue type."""
        input_text = failure.get("input", "")
        expected = failure.get("expected", "")
        actual = failure.get("actual", "")

        issues = []

        # Text formatting issues
        if expected.endswith((".", "!", "?")) and not actual.endswith((".", "!", "?")):
            issues.append("missing_punctuation")

        # Capitalization
        if expected and actual:
            if expected[0].isupper() and actual[0].islower():
                issues.append("missing_capitalization")
            elif expected[0].islower() and actual[0].isupper():
                issues.append("incorrect_capitalization")

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

        # Number conversions
        if re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\b", input_text):
            if re.search(r"\d", expected) and not re.search(r"\d", actual):
                issues.append("number_word")

        # Time/currency
        if " PM" in expected or " AM" in expected:
            issues.append("time_format")
        if "$" in expected and ("dollars" in actual or "cents" in actual):
            issues.append("currency_format")

        # Main category based on test module
        module = failure.get("module", "")
        if "web" in module:
            category = "web_entities"
        elif "code" in module:
            category = "code_entities"
        elif "numeric" in module:
            category = "numeric_entities"
        elif "time" in module:
            category = "temporal_entities"
        elif "financial" in module:
            category = "financial_entities"
        elif "math" in module:
            category = "math_entities"
        else:
            category = "text_formatting"

        return category, issues or ["unknown"]

    def generate_report(self, format: str = "yaml") -> Dict:
        """Generate the analysis report."""
        # Group by unique issue patterns
        issue_groups = defaultdict(list)

        for failure in self.failures:
            category, issues = self.categorize_issue(failure)
            issue_key = tuple(sorted(issues))
            failure["category"] = category
            failure["issues"] = issues
            issue_groups[issue_key].append(failure)

        # Build report structure
        report = {
            "test_failure_analysis": {
                "summary": {
                    "total_tests": self.total,
                    "passed": self.passed,
                    "failed": len(self.failures),
                    "unique_patterns": len(issue_groups),
                    "generated_at": datetime.now().isoformat(),
                },
                "issues": [],
            }
        }

        # Add issues sorted by frequency
        for issue_pattern, failures in sorted(issue_groups.items(), key=lambda x: -len(x[1])):
            issue_name = " + ".join(issue_pattern)

            # Group by category
            by_category = defaultdict(list)
            for f in failures:
                by_category[f["category"]].append(f)

            issue_data = {
                "pattern": issue_name,
                "count": len(failures),
                "categories": list(by_category.keys()),
                "examples": [],
            }

            # Add examples (up to 3)
            for f in failures[:3]:
                issue_data["examples"].append(
                    {"test": f["test"], "input": f["input"], "expected": f["expected"], "actual": f["actual"]}
                )

            if len(failures) > 3:
                issue_data["additional_tests"] = [f["test"] for f in failures[3:]]

            report["test_failure_analysis"]["issues"].append(issue_data)

        return report

    def save_report(self, filepath: Path, format: str = "yaml"):
        """Save the report to file."""
        report = self.generate_report(format)

        with open(filepath, "w") as f:
            if format == "yaml":
                yaml.dump(report, f, default_flow_style=False, sort_keys=False, width=120, indent=2, allow_unicode=True)
            elif format == "json":
                json.dump(report, f, indent=2)
            else:
                raise ValueError(f"Unknown format: {format}")

        return filepath


# Plugin implementation
_analyzer = None


def pytest_configure(config):
    """Configure the plugin."""
    summary_format = config.getoption("--summary", None)
    if summary_format:
        global _analyzer
        _analyzer = FailureAnalyzer()
        config.pluginmanager.register(_analyzer, "failure_analyzer")


def pytest_addoption(parser):
    """Add command line options."""
    parser.addoption(
        "--summary",
        action="store",
        choices=["yaml", "json", "compact"],
        help="Generate failure summary in specified format",
    )
    parser.addoption("--summary-file", action="store", help="Output file for summary (default: test_summary.<format>)")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture test results."""
    global _analyzer

    if _analyzer is None:
        yield
        return

    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        passed = report.outcome == "passed"
        failure_info = None

        if not passed and hasattr(report, "longrepr"):
            longrepr = str(report.longrepr)
            failure_info = _analyzer.extract_failure_info(longrepr)

        _analyzer.add_result(item.nodeid, passed, failure_info)


def pytest_sessionfinish(session, exitstatus):
    """Generate report at end of session."""
    global _analyzer

    if _analyzer and _analyzer.failures:
        format = session.config.getoption("--summary")
        output_file = session.config.getoption("--summary-file")

        if not output_file:
            output_file = f"test_summary.{format}"

        filepath = _analyzer.save_report(Path(output_file), format)

        # Print summary
        print("\n📊 Test Failure Summary")
        print(f"   Format: {format.upper()}")
        print(f"   File: {filepath}")
        print(f"   Failed: {len(_analyzer.failures)} | Passed: {_analyzer.passed} | Total: {_analyzer.total}")
        print(f"   Unique Issues: {len(_analyzer.generate_report()['test_failure_analysis']['issues'])}")

        # Show top issues
        report = _analyzer.generate_report()
        print("\n   Top Issues:")
        for issue in report["test_failure_analysis"]["issues"][:5]:
            print(f"   • {issue['pattern']} ({issue['count']} occurrences)")
