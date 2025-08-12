#!/usr/bin/env python3
"""
Pattern Coverage Plugin for pytest

This plugin integrates the pattern testing infrastructure with pytest to provide
seamless pattern coverage analysis during test runs.

PHASE 24: Pattern Testing Infrastructure - pytest Integration
"""

import pytest
import json
import time
from typing import Dict, Any, Optional
from pathlib import Path

from stt.core.config import setup_logging
from stt.text_formatting.pattern_test_runner import (
    PatternTestRunner,
    PatternTestValidator,
    run_pattern_testing_infrastructure,
    validate_pattern_testing_infrastructure
)

logger = setup_logging(__name__)


class PatternCoveragePlugin:
    """pytest plugin for pattern coverage analysis."""
    
    def __init__(self):
        self.runner = PatternTestRunner()
        self.validator = PatternTestValidator()
        self.start_time: Optional[float] = None
        self.results: Optional[Dict[str, Any]] = None
        self.enabled = False
    
    def pytest_addoption(self, parser):
        """Add command line options for pattern coverage."""
        group = parser.getgroup("pattern_coverage")
        group.addoption(
            "--pattern-coverage",
            action="store_true",
            default=False,
            help="Run pattern coverage analysis during tests"
        )
        group.addoption(
            "--pattern-coverage-report",
            action="store",
            default=None,
            metavar="PATH",
            help="Export pattern coverage report to specified path"
        )
        group.addoption(
            "--pattern-coverage-validate",
            action="store_true",
            default=False,
            help="Validate pattern testing infrastructure"
        )
    
    def pytest_configure(self, config):
        """Configure the plugin based on command line options."""
        self.enabled = config.getoption("--pattern-coverage")
        self.validate_only = config.getoption("--pattern-coverage-validate")
        self.report_path = config.getoption("--pattern-coverage-report")
        
        if self.enabled or self.validate_only:
            # Register this plugin
            config.pluginmanager.register(self, "pattern_coverage")
    
    def pytest_sessionstart(self, session):
        """Run pattern coverage analysis at session start if enabled."""
        if self.validate_only:
            self._run_validation(session)
        elif self.enabled:
            self._run_pattern_coverage(session)
    
    def pytest_sessionfinish(self, session, exitstatus):
        """Export results at session finish if requested."""
        if self.results and self.report_path:
            self._export_results(session)
    
    def _run_validation(self, session):
        """Run pattern testing infrastructure validation."""
        session.config.option.verbose = max(session.config.option.verbose, 1)
        
        logger.info("Validating pattern testing infrastructure...")
        validation_results = validate_pattern_testing_infrastructure()
        
        if validation_results["infrastructure_healthy"]:
            logger.info("✓ Pattern testing infrastructure validation passed")
            self._print_validation_details(validation_results)
        else:
            logger.error("✗ Pattern testing infrastructure validation failed")
            self._print_validation_details(validation_results)
            pytest.exit("Pattern testing infrastructure validation failed", 1)
    
    def _run_pattern_coverage(self, session):
        """Run pattern coverage analysis."""
        session.config.option.verbose = max(session.config.option.verbose, 1)
        
        logger.info("Running pattern coverage analysis...")
        self.start_time = time.perf_counter()
        
        try:
            self.results = run_pattern_testing_infrastructure()
            
            if self.results["success"]:
                execution_time = (time.perf_counter() - self.start_time) * 1000
                logger.info(f"✓ Pattern coverage analysis completed in {execution_time:.1f}ms")
                self._print_coverage_summary(self.results)
            else:
                logger.error("✗ Pattern coverage analysis failed")
                pytest.exit("Pattern coverage analysis failed", 1)
                
        except Exception as e:
            logger.error(f"Pattern coverage analysis error: {e}")
            pytest.exit(f"Pattern coverage analysis error: {e}", 1)
    
    def _print_validation_details(self, validation_results: Dict[str, Any]):
        """Print validation details."""
        details = validation_results.get("details", {})
        
        print("\nPattern Testing Infrastructure Validation:")
        print(f"  Pattern Discovery: {'✓' if validation_results['pattern_discovery'] else '✗'}")
        if "patterns_discovered" in details:
            print(f"    Patterns discovered: {details['patterns_discovered']}")
        
        print(f"  Test Generation: {'✓' if validation_results['test_generation'] else '✗'}")
        if "test_cases_generated" in details:
            print(f"    Test cases generated: {details['test_cases_generated']}")
        
        print(f"  Coverage Analysis: {'✓' if validation_results['coverage_analysis'] else '✗'}")
        if "coverage_reports_generated" in details:
            print(f"    Coverage reports: {details['coverage_reports_generated']}")
        
        print(f"  Test Execution: {'✓' if validation_results['test_execution'] else '✗'}")
        if "sample_test_execution" in details:
            sample = details["sample_test_execution"]
            print(f"    Sample execution: {sample['tests_run']} tests, {sample['success_rate']:.1f}% success")
        
        if "error" in details:
            print(f"  Error: {details['error']}")
    
    def _print_coverage_summary(self, results: Dict[str, Any]):
        """Print coverage analysis summary."""
        summary = results["summary"]
        
        print("\nPattern Coverage Analysis Results:")
        print(f"  Total Patterns: {summary['total_patterns']}")
        print(f"  Total Test Cases: {summary['total_tests']}")
        print(f"  Test Success Rate: {summary['success_rate']:.1f}%")
        print(f"  Pattern Coverage: {summary['coverage']:.1f}%")
        print(f"  Target Achieved (95%): {'✓' if summary['target_achieved'] else '✗'}")
        print(f"  Execution Time: {results['execution_time_ms']:.1f}ms")
        
        if results.get("recommendations"):
            print("\nRecommendations:")
            for i, rec in enumerate(results["recommendations"][:3], 1):
                print(f"  {i}. {rec}")
    
    def _export_results(self, session):
        """Export pattern coverage results to file."""
        try:
            output_path = Path(self.report_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, default=str)
            
            logger.info(f"Pattern coverage report exported to {output_path}")
            print(f"\nPattern coverage report saved to: {output_path}")
            
        except Exception as e:
            logger.warning(f"Failed to export pattern coverage report: {e}")


# Hook functions for pytest plugin registration
def pytest_addoption(parser):
    """Add command line options for pattern coverage."""
    plugin = PatternCoveragePlugin()
    plugin.pytest_addoption(parser)


def pytest_configure(config):
    """Configure the plugin."""
    plugin = PatternCoveragePlugin()
    plugin.pytest_configure(config)


def pytest_sessionstart(session):
    """Run at session start."""
    if hasattr(session.config, '_pattern_coverage_plugin'):
        session.config._pattern_coverage_plugin.pytest_sessionstart(session)


def pytest_sessionfinish(session, exitstatus):
    """Run at session finish."""
    if hasattr(session.config, '_pattern_coverage_plugin'):
        session.config._pattern_coverage_plugin.pytest_sessionfinish(session, exitstatus)


# Test classes for pattern infrastructure validation
class TestPatternTestingInfrastructure:
    """Tests for the pattern testing infrastructure itself."""
    
    def test_pattern_discovery_framework(self):
        """Test that pattern discovery framework works."""
        from stt.text_formatting.pattern_test_auto_generator import PatternDiscovery
        
        discovery = PatternDiscovery()
        patterns = discovery.discover_all_patterns()
        
        # Verify we discovered patterns
        assert len(patterns) > 0, "Should discover at least some patterns"
        
        # Verify pattern info structure
        for pattern_name, pattern_info in patterns.items():
            assert hasattr(pattern_info, 'name'), f"Pattern {pattern_name} missing name"
            assert hasattr(pattern_info, 'pattern_object'), f"Pattern {pattern_name} missing pattern_object"
            assert hasattr(pattern_info, 'category'), f"Pattern {pattern_name} missing category"
            assert hasattr(pattern_info, 'source_module'), f"Pattern {pattern_name} missing source_module"
    
    def test_test_case_generation_framework(self):
        """Test that test case generation framework works."""
        from stt.text_formatting.pattern_test_auto_generator import TestCaseGenerator
        
        generator = TestCaseGenerator()
        all_test_cases = generator.generate_test_cases_for_all_patterns()
        
        # Verify test cases were generated
        assert len(all_test_cases) > 0, "Should generate test cases for patterns"
        
        # Verify test case structure
        for pattern_name, test_cases in all_test_cases.items():
            assert isinstance(test_cases, list), f"Test cases for {pattern_name} should be a list"
            
            for test_case in test_cases[:3]:  # Check first 3
                assert hasattr(test_case, 'input_text'), "Test case missing input_text"
                assert hasattr(test_case, 'expected_match'), "Test case missing expected_match"
                assert hasattr(test_case, 'test_type'), "Test case missing test_type"
                assert hasattr(test_case, 'pattern_name'), "Test case missing pattern_name"
                assert hasattr(test_case, 'description'), "Test case missing description"
    
    def test_coverage_analysis_framework(self):
        """Test that coverage analysis framework works."""
        from stt.text_formatting.pattern_test_auto_generator import PatternCoverageAnalyzer
        
        analyzer = PatternCoverageAnalyzer()
        coverage_reports = analyzer.analyze_all_patterns_coverage()
        
        # Verify coverage reports were generated
        assert len(coverage_reports) > 0, "Should generate coverage reports"
        
        # Verify coverage report structure
        for pattern_name, report in coverage_reports.items():
            assert hasattr(report, 'pattern_name'), "Report missing pattern_name"
            assert hasattr(report, 'coverage_percentage'), "Report missing coverage_percentage"
            assert hasattr(report, 'total_branches'), "Report missing total_branches"
            assert hasattr(report, 'covered_branches'), "Report missing covered_branches"
            assert hasattr(report, 'generated_tests'), "Report missing generated_tests"
            
            # Verify coverage percentage is valid
            assert 0 <= report.coverage_percentage <= 100, f"Invalid coverage percentage: {report.coverage_percentage}"
    
    def test_pattern_test_runner_framework(self):
        """Test that pattern test runner framework works."""
        runner = PatternTestRunner()
        
        # Test infrastructure validation
        validator = PatternTestValidator()
        validation_results = validator.validate_infrastructure()
        
        assert validation_results["infrastructure_healthy"], "Infrastructure should be healthy"
        assert validation_results["pattern_discovery"], "Pattern discovery should work"
        assert validation_results["test_generation"], "Test generation should work"
        assert validation_results["coverage_analysis"], "Coverage analysis should work"
        assert validation_results["test_execution"], "Test execution should work"
    
    def test_pattern_coverage_target_measurement(self):
        """Test that pattern coverage can be measured against 95% target."""
        results = run_pattern_testing_infrastructure()
        
        assert results["success"], "Pattern testing infrastructure should run successfully"
        
        summary = results["summary"]
        assert "coverage" in summary, "Summary should include coverage"
        assert "target_achieved" in summary, "Summary should include target achievement"
        assert isinstance(summary["coverage"], (int, float)), "Coverage should be numeric"
        assert isinstance(summary["target_achieved"], bool), "Target achieved should be boolean"
        
        # Coverage should be measurable (0-100%)
        assert 0 <= summary["coverage"] <= 100, f"Coverage should be 0-100%, got {summary['coverage']}"
    
    def test_pattern_testing_infrastructure_integration(self):
        """Test complete integration of pattern testing infrastructure."""
        # This test validates the full workflow
        validation = validate_pattern_testing_infrastructure()
        assert validation["infrastructure_healthy"], "Infrastructure should be healthy"
        
        # Run pattern testing
        results = run_pattern_testing_infrastructure()
        assert results["success"], "Pattern testing should succeed"
        
        # Verify comprehensive results
        summary = results["summary"]
        assert summary["total_patterns"] > 0, "Should test some patterns"
        assert summary["total_tests"] > 0, "Should generate some tests"
        assert 0 <= summary["success_rate"] <= 100, "Success rate should be valid percentage"
        assert 0 <= summary["coverage"] <= 100, "Coverage should be valid percentage"
        
        # Test pytest export capability
        from stt.text_formatting.pattern_test_runner import export_pattern_tests_as_pytest
        pytest_file = export_pattern_tests_as_pytest("/tmp/test_pattern_export.py")
        
        # Verify file was created
        assert Path(pytest_file).exists(), "Pytest file should be created"
        
        # Verify file has content
        with open(pytest_file, 'r') as f:
            content = f.read()
        assert "class TestAutoGeneratedPatterns" in content, "Pytest file should contain test class"
        assert "def test_" in content, "Pytest file should contain test methods"


# Fixture for pattern testing infrastructure
@pytest.fixture(scope="session")
def pattern_testing_infrastructure():
    """Fixture that provides pattern testing infrastructure results."""
    return run_pattern_testing_infrastructure()


@pytest.fixture(scope="session")
def pattern_coverage_validation():
    """Fixture that validates pattern testing infrastructure."""
    return validate_pattern_testing_infrastructure()


# Markers for pattern testing
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "pattern_infrastructure: mark test as pattern infrastructure test"
    )
    config.addinivalue_line(
        "markers", "pattern_coverage: mark test as pattern coverage test"
    )


if __name__ == "__main__":
    # Run pattern testing infrastructure validation
    print("=== Pattern Testing Infrastructure Plugin Test ===")
    
    # Test infrastructure validation
    validation = validate_pattern_testing_infrastructure()
    print(f"Infrastructure healthy: {validation['infrastructure_healthy']}")
    
    if validation["infrastructure_healthy"]:
        # Test pattern coverage
        results = run_pattern_testing_infrastructure()
        print(f"Pattern coverage: {results['summary']['coverage']:.1f}%")
        print(f"Target achieved: {results['summary']['target_achieved']}")
        print("✓ Pattern testing infrastructure plugin working correctly")
    else:
        print("✗ Pattern testing infrastructure validation failed")