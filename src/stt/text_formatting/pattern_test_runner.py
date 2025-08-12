#!/usr/bin/env python3
"""
Pattern Test Runner for Comprehensive Pattern Validation

This module provides a test runner that integrates auto-generated pattern tests
with the existing test infrastructure to achieve 95% pattern coverage.

PHASE 24: Pattern Testing Infrastructure - Test Runner Component
"""

from __future__ import annotations

import time
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from stt.core.config import setup_logging
from stt.text_formatting.pattern_test_auto_generator import (
    PatternTestFramework, 
    PatternCoverageReport,
    GeneratedTestCase,
    TestCaseType
)

logger = setup_logging(__name__)


@dataclass
class TestExecutionResult:
    """Result of executing a generated test case."""
    test_case: GeneratedTestCase
    actual_match: bool
    expected_match: bool
    passed: bool
    execution_time_ms: float
    error_message: Optional[str] = None


@dataclass
class PatternTestResult:
    """Results of testing a specific pattern."""
    pattern_name: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    success_rate: float
    execution_results: List[TestExecutionResult] = field(default_factory=list)
    coverage_report: Optional[PatternCoverageReport] = None


@dataclass
class FrameworkTestSummary:
    """Summary of all pattern testing framework results."""
    total_patterns: int
    total_tests: int
    total_passed: int
    total_failed: int
    overall_success_rate: float
    average_coverage: float
    target_coverage_achieved: bool
    pattern_results: Dict[str, PatternTestResult] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    recommendations: List[str] = field(default_factory=list)


class PatternTestRunner:
    """Executes and validates auto-generated pattern tests."""
    
    def __init__(self):
        self.framework = PatternTestFramework()
        self.execution_results: Dict[str, List[TestExecutionResult]] = {}
    
    def run_all_pattern_tests(self) -> FrameworkTestSummary:
        """Run all auto-generated pattern tests and return comprehensive results."""
        logger.info("Starting comprehensive pattern test execution")
        start_time = time.perf_counter()
        
        # Get all coverage reports (includes test generation)
        coverage_reports = self.framework.analyzer.analyze_all_patterns_coverage()
        
        # Execute tests for each pattern
        pattern_results = {}
        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_coverage = 0.0
        
        for pattern_name, coverage_report in coverage_reports.items():
            try:
                result = self._execute_pattern_tests(pattern_name, coverage_report)
                pattern_results[pattern_name] = result
                
                total_tests += result.total_tests
                total_passed += result.passed_tests
                total_failed += result.failed_tests
                total_coverage += coverage_report.coverage_percentage
                
            except Exception as e:
                logger.warning(f"Failed to execute tests for pattern {pattern_name}: {e}")
                # Create empty result for failed pattern
                pattern_results[pattern_name] = PatternTestResult(
                    pattern_name=pattern_name,
                    total_tests=0,
                    passed_tests=0,
                    failed_tests=1,
                    success_rate=0.0
                )
        
        # Calculate summary metrics
        execution_time = (time.perf_counter() - start_time) * 1000
        overall_success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0.0
        average_coverage = total_coverage / len(coverage_reports) if coverage_reports else 0.0
        target_achieved = average_coverage >= 95.0
        
        # Generate recommendations
        recommendations = self._generate_test_recommendations(pattern_results, average_coverage)
        
        summary = FrameworkTestSummary(
            total_patterns=len(coverage_reports),
            total_tests=total_tests,
            total_passed=total_passed,
            total_failed=total_failed,
            overall_success_rate=overall_success_rate,
            average_coverage=average_coverage,
            target_coverage_achieved=target_achieved,
            pattern_results=pattern_results,
            execution_time_ms=execution_time,
            recommendations=recommendations
        )
        
        logger.info(
            f"Pattern test execution complete. "
            f"Success rate: {overall_success_rate:.1f}%, "
            f"Coverage: {average_coverage:.1f}%, "
            f"Time: {execution_time:.1f}ms"
        )
        
        return summary
    
    def _execute_pattern_tests(self, pattern_name: str, coverage_report: PatternCoverageReport) -> PatternTestResult:
        """Execute tests for a specific pattern."""
        pattern_info = self.framework.discovery.discovered_patterns.get(pattern_name)
        if not pattern_info:
            raise ValueError(f"Pattern {pattern_name} not found in discovery")
        
        execution_results = []
        passed_tests = 0
        failed_tests = 0
        
        for test_case in coverage_report.generated_tests:
            try:
                result = self._execute_single_test(pattern_info.pattern_object, test_case)
                execution_results.append(result)
                
                if result.passed:
                    passed_tests += 1
                else:
                    failed_tests += 1
                    
            except Exception as e:
                logger.debug(f"Error executing test case for {pattern_name}: {e}")
                # Create failed result
                failed_result = TestExecutionResult(
                    test_case=test_case,
                    actual_match=False,
                    expected_match=test_case.expected_match,
                    passed=False,
                    execution_time_ms=0.0,
                    error_message=str(e)
                )
                execution_results.append(failed_result)
                failed_tests += 1
        
        total_tests = len(coverage_report.generated_tests)
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0.0
        
        return PatternTestResult(
            pattern_name=pattern_name,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            success_rate=success_rate,
            execution_results=execution_results,
            coverage_report=coverage_report
        )
    
    def _execute_single_test(self, pattern, test_case: GeneratedTestCase) -> TestExecutionResult:
        """Execute a single test case against a pattern."""
        start_time = time.perf_counter()
        
        try:
            # Test the pattern against the input
            match = pattern.search(test_case.input_text)
            actual_match = match is not None
            
            # Check if result matches expectation
            passed = actual_match == test_case.expected_match
            
            execution_time = (time.perf_counter() - start_time) * 1000
            
            return TestExecutionResult(
                test_case=test_case,
                actual_match=actual_match,
                expected_match=test_case.expected_match,
                passed=passed,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000
            
            return TestExecutionResult(
                test_case=test_case,
                actual_match=False,
                expected_match=test_case.expected_match,
                passed=False,
                execution_time_ms=execution_time,
                error_message=str(e)
            )
    
    def _generate_test_recommendations(self, pattern_results: Dict[str, PatternTestResult], average_coverage: float) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        # Coverage recommendations
        if average_coverage < 95.0:
            recommendations.append(
                f"Average pattern coverage is {average_coverage:.1f}%. "
                f"Target is 95%. Consider improving test case generation."
            )
        
        # Pattern-specific recommendations
        low_success_patterns = [
            name for name, result in pattern_results.items()
            if result.success_rate < 80.0
        ]
        
        if low_success_patterns:
            recommendations.append(
                f"{len(low_success_patterns)} patterns have success rate below 80%: "
                f"{', '.join(low_success_patterns[:5])}{'...' if len(low_success_patterns) > 5 else ''}"
            )
        
        # Test type analysis
        test_type_performance = self._analyze_test_type_performance(pattern_results)
        for test_type, success_rate in test_type_performance.items():
            if success_rate < 70.0:
                recommendations.append(
                    f"Test type '{test_type}' has low success rate ({success_rate:.1f}%). "
                    f"Review test case generation for this type."
                )
        
        # Performance recommendations
        slow_patterns = [
            name for name, result in pattern_results.items()
            if result.execution_results and 
            sum(r.execution_time_ms for r in result.execution_results) / len(result.execution_results) > 10.0
        ]
        
        if slow_patterns:
            recommendations.append(
                f"{len(slow_patterns)} patterns have slow execution times. "
                f"Consider optimizing: {', '.join(slow_patterns[:3])}"
            )
        
        if not recommendations:
            recommendations.append(
                "Excellent results! All patterns meet performance and coverage targets."
            )
        
        return recommendations
    
    def _analyze_test_type_performance(self, pattern_results: Dict[str, PatternTestResult]) -> Dict[str, float]:
        """Analyze performance by test type."""
        test_type_stats = {}
        
        for result in pattern_results.values():
            for exec_result in result.execution_results:
                test_type = exec_result.test_case.test_type.value
                
                if test_type not in test_type_stats:
                    test_type_stats[test_type] = {"passed": 0, "total": 0}
                
                test_type_stats[test_type]["total"] += 1
                if exec_result.passed:
                    test_type_stats[test_type]["passed"] += 1
        
        # Calculate success rates
        test_type_performance = {}
        for test_type, stats in test_type_stats.items():
            success_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0.0
            test_type_performance[test_type] = success_rate
        
        return test_type_performance
    
    def export_results(self, summary: FrameworkTestSummary, output_path: str) -> str:
        """Export test results to a JSON file."""
        # Convert dataclasses to dict for JSON serialization
        export_data = {
            "summary": {
                "total_patterns": summary.total_patterns,
                "total_tests": summary.total_tests,
                "total_passed": summary.total_passed,
                "total_failed": summary.total_failed,
                "overall_success_rate": summary.overall_success_rate,
                "average_coverage": summary.average_coverage,
                "target_coverage_achieved": summary.target_coverage_achieved,
                "execution_time_ms": summary.execution_time_ms,
                "recommendations": summary.recommendations
            },
            "pattern_results": {
                name: {
                    "pattern_name": result.pattern_name,
                    "total_tests": result.total_tests,
                    "passed_tests": result.passed_tests,
                    "failed_tests": result.failed_tests,
                    "success_rate": result.success_rate,
                    "coverage_percentage": result.coverage_report.coverage_percentage if result.coverage_report else 0.0,
                    "failed_test_cases": [
                        {
                            "input_text": exec_result.test_case.input_text,
                            "expected_match": exec_result.expected_match,
                            "actual_match": exec_result.actual_match,
                            "test_type": exec_result.test_case.test_type.value,
                            "error": exec_result.error_message
                        }
                        for exec_result in result.execution_results
                        if not exec_result.passed
                    ][:5]  # Limit to 5 failed cases per pattern
                }
                for name, result in summary.pattern_results.items()
            },
            "metadata": {
                "framework_version": "1.0.0",
                "test_infrastructure": "auto_generated",
                "timestamp": time.time(),
                "target_coverage": 95.0
            }
        }
        
        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        logger.info(f"Test results exported to {output_file}")
        return str(output_file)
    
    def generate_coverage_report(self, summary: FrameworkTestSummary) -> str:
        """Generate a human-readable coverage report."""
        report_lines = []
        
        report_lines.append("=" * 80)
        report_lines.append("PATTERN TESTING INFRASTRUCTURE - COVERAGE REPORT")
        report_lines.append("=" * 80)
        
        # Summary section
        report_lines.append(f"\nSUMMARY:")
        report_lines.append(f"  Total Patterns Tested: {summary.total_patterns}")
        report_lines.append(f"  Total Test Cases: {summary.total_tests}")
        report_lines.append(f"  Test Success Rate: {summary.overall_success_rate:.1f}%")
        report_lines.append(f"  Average Coverage: {summary.average_coverage:.1f}%")
        report_lines.append(f"  Target Coverage (95%): {'✓ ACHIEVED' if summary.target_coverage_achieved else '✗ NOT ACHIEVED'}")
        report_lines.append(f"  Execution Time: {summary.execution_time_ms:.1f}ms")
        
        # Coverage breakdown
        report_lines.append(f"\nCOVERAGE BREAKDOWN:")
        high_coverage = [name for name, result in summary.pattern_results.items() 
                        if result.coverage_report and result.coverage_report.coverage_percentage >= 95.0]
        medium_coverage = [name for name, result in summary.pattern_results.items() 
                          if result.coverage_report and 70.0 <= result.coverage_report.coverage_percentage < 95.0]
        low_coverage = [name for name, result in summary.pattern_results.items() 
                       if result.coverage_report and result.coverage_report.coverage_percentage < 70.0]
        
        report_lines.append(f"  High Coverage (95%+): {len(high_coverage)} patterns")
        report_lines.append(f"  Medium Coverage (70-94%): {len(medium_coverage)} patterns")
        report_lines.append(f"  Low Coverage (<70%): {len(low_coverage)} patterns")
        
        # Pattern details (top performers and needs improvement)
        if high_coverage:
            report_lines.append(f"\nTOP PERFORMING PATTERNS:")
            for pattern_name in high_coverage[:5]:
                result = summary.pattern_results[pattern_name]
                coverage = result.coverage_report.coverage_percentage if result.coverage_report else 0.0
                report_lines.append(f"  ✓ {pattern_name}: {coverage:.1f}% coverage, {result.success_rate:.1f}% success")
        
        if low_coverage:
            report_lines.append(f"\nPATTERNS NEEDING IMPROVEMENT:")
            for pattern_name in low_coverage[:5]:
                result = summary.pattern_results[pattern_name]
                coverage = result.coverage_report.coverage_percentage if result.coverage_report else 0.0
                report_lines.append(f"  ⚠ {pattern_name}: {coverage:.1f}% coverage, {result.success_rate:.1f}% success")
        
        # Recommendations
        if summary.recommendations:
            report_lines.append(f"\nRECOMMENDATIONS:")
            for i, recommendation in enumerate(summary.recommendations, 1):
                report_lines.append(f"  {i}. {recommendation}")
        
        # Test infrastructure validation
        report_lines.append(f"\nTEST INFRASTRUCTURE VALIDATION:")
        report_lines.append(f"  ✓ Pattern Discovery: {summary.total_patterns} patterns found")
        report_lines.append(f"  ✓ Test Generation: {summary.total_tests} test cases generated")
        report_lines.append(f"  ✓ Coverage Analysis: Functional")
        report_lines.append(f"  ✓ Test Execution: {summary.total_passed} passed, {summary.total_failed} failed")
        
        report_lines.append("\n" + "=" * 80)
        report_lines.append("END REPORT")
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)


class PatternTestValidator:
    """Validates that the pattern testing infrastructure works correctly."""
    
    def __init__(self):
        self.runner = PatternTestRunner()
    
    def validate_infrastructure(self) -> Dict[str, Any]:
        """Validate that the pattern testing infrastructure is working."""
        validation_results = {
            "pattern_discovery": False,
            "test_generation": False,
            "coverage_analysis": False,
            "test_execution": False,
            "infrastructure_healthy": False,
            "details": {}
        }
        
        try:
            # Test pattern discovery
            patterns = self.runner.framework.discovery.discover_all_patterns()
            validation_results["pattern_discovery"] = len(patterns) > 0
            validation_results["details"]["patterns_discovered"] = len(patterns)
            
            # Test test generation
            test_cases = self.runner.framework.generator.generate_test_cases_for_all_patterns()
            total_tests = sum(len(cases) for cases in test_cases.values())
            validation_results["test_generation"] = total_tests > 0
            validation_results["details"]["test_cases_generated"] = total_tests
            
            # Test coverage analysis
            coverage_reports = self.runner.framework.analyzer.analyze_all_patterns_coverage()
            validation_results["coverage_analysis"] = len(coverage_reports) > 0
            validation_results["details"]["coverage_reports_generated"] = len(coverage_reports)
            
            # Test execution (run a small subset)
            if coverage_reports:
                sample_pattern = list(coverage_reports.keys())[0]
                sample_report = coverage_reports[sample_pattern]
                sample_result = self.runner._execute_pattern_tests(sample_pattern, sample_report)
                validation_results["test_execution"] = True
                validation_results["details"]["sample_test_execution"] = {
                    "pattern": sample_pattern,
                    "tests_run": sample_result.total_tests,
                    "success_rate": sample_result.success_rate
                }
            
            # Overall infrastructure health
            validation_results["infrastructure_healthy"] = all([
                validation_results["pattern_discovery"],
                validation_results["test_generation"], 
                validation_results["coverage_analysis"],
                validation_results["test_execution"]
            ])
            
        except Exception as e:
            validation_results["details"]["error"] = str(e)
            logger.warning(f"Infrastructure validation failed: {e}")
        
        return validation_results


# Convenience functions for testing infrastructure
def run_pattern_testing_infrastructure() -> Dict[str, Any]:
    """Run the complete pattern testing infrastructure and return results."""
    runner = PatternTestRunner()
    summary = runner.run_all_pattern_tests()
    
    return {
        "success": True,
        "summary": {
            "total_patterns": summary.total_patterns,
            "total_tests": summary.total_tests,
            "success_rate": summary.overall_success_rate,
            "coverage": summary.average_coverage,
            "target_achieved": summary.target_coverage_achieved
        },
        "execution_time_ms": summary.execution_time_ms,
        "recommendations": summary.recommendations
    }


def validate_pattern_testing_infrastructure() -> Dict[str, Any]:
    """Validate that the pattern testing infrastructure is working correctly."""
    validator = PatternTestValidator()
    return validator.validate_infrastructure()


def export_pattern_tests_as_pytest(output_path: str = "/tmp/auto_generated_pattern_tests.py") -> str:
    """Export auto-generated pattern tests as pytest file."""
    framework = PatternTestFramework()
    return framework.export_test_cases_as_pytest(output_path)


if __name__ == "__main__":
    # Run infrastructure validation
    print("=== Pattern Testing Infrastructure Validation ===")
    validation = validate_pattern_testing_infrastructure()
    
    if validation["infrastructure_healthy"]:
        print("✓ Infrastructure validation passed")
        
        # Run full pattern testing
        print("\n=== Running Pattern Testing Infrastructure ===")
        results = run_pattern_testing_infrastructure()
        
        print(f"✓ Tested {results['summary']['total_patterns']} patterns")
        print(f"✓ Generated {results['summary']['total_tests']} test cases")
        print(f"✓ Success rate: {results['summary']['success_rate']:.1f}%")
        print(f"✓ Coverage: {results['summary']['coverage']:.1f}%")
        print(f"✓ Target achieved: {results['summary']['target_achieved']}")
        
        # Export pytest file
        pytest_file = export_pattern_tests_as_pytest()
        print(f"✓ Exported tests to: {pytest_file}")
        
    else:
        print("✗ Infrastructure validation failed")
        print("Details:", validation["details"])