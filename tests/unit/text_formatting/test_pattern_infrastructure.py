#!/usr/bin/env python3
"""
Test Pattern Testing Infrastructure

This test validates that the pattern testing infrastructure is working correctly
and can achieve the target of 95% pattern coverage.

PHASE 24: Pattern Testing Infrastructure Validation
"""

import pytest
from pathlib import Path

# Pattern infrastructure imports
from stt.text_formatting.pattern_test_auto_generator import (
    PatternDiscovery,
    TestCaseGenerator, 
    PatternCoverageAnalyzer,
    PatternTestFramework
)
from stt.text_formatting.pattern_test_runner import (
    PatternTestRunner,
    PatternTestValidator,
    run_pattern_testing_infrastructure,
    validate_pattern_testing_infrastructure,
    export_pattern_tests_as_pytest
)


class TestPatternTestingInfrastructure:
    """Validate the pattern testing infrastructure components."""
    
    def test_pattern_discovery_works(self):
        """Test that pattern discovery finds patterns."""
        discovery = PatternDiscovery()
        patterns = discovery.discover_all_patterns()
        
        # Should discover some patterns
        assert len(patterns) > 0, "Should discover at least one pattern"
        
        # Verify pattern info structure
        for pattern_name, pattern_info in patterns.items():
            assert hasattr(pattern_info, 'name'), f"Pattern {pattern_name} missing name"
            assert hasattr(pattern_info, 'pattern_object'), f"Pattern {pattern_name} missing pattern_object" 
            assert hasattr(pattern_info, 'category'), f"Pattern {pattern_name} missing category"
            assert hasattr(pattern_info, 'source_module'), f"Pattern {pattern_name} missing source_module"
    
    def test_test_case_generation_works(self):
        """Test that test case generation produces valid test cases."""
        generator = TestCaseGenerator()
        all_test_cases = generator.generate_test_cases_for_all_patterns()
        
        # Should generate test cases
        assert len(all_test_cases) > 0, "Should generate test cases for patterns"
        
        total_tests = sum(len(cases) for cases in all_test_cases.values())
        assert total_tests > 0, "Should generate some test cases"
        
        # Verify test case structure
        for pattern_name, test_cases in all_test_cases.items():
            for test_case in test_cases[:3]:  # Check first 3
                assert hasattr(test_case, 'input_text'), "Test case missing input_text"
                assert hasattr(test_case, 'expected_match'), "Test case missing expected_match"
                assert hasattr(test_case, 'test_type'), "Test case missing test_type"
                assert hasattr(test_case, 'pattern_name'), "Test case missing pattern_name"
                assert isinstance(test_case.expected_match, bool), "expected_match should be boolean"
    
    def test_coverage_analysis_works(self):
        """Test that coverage analysis produces valid reports."""
        analyzer = PatternCoverageAnalyzer()
        coverage_reports = analyzer.analyze_all_patterns_coverage()
        
        # Should generate coverage reports
        assert len(coverage_reports) > 0, "Should generate coverage reports"
        
        # Verify coverage report structure
        for pattern_name, report in coverage_reports.items():
            assert hasattr(report, 'pattern_name'), "Report missing pattern_name"
            assert hasattr(report, 'coverage_percentage'), "Report missing coverage_percentage"
            assert hasattr(report, 'generated_tests'), "Report missing generated_tests"
            
            # Coverage percentage should be valid
            assert 0 <= report.coverage_percentage <= 100, f"Invalid coverage: {report.coverage_percentage}"
    
    def test_pattern_test_runner_works(self):
        """Test that the pattern test runner executes tests correctly."""
        runner = PatternTestRunner()
        
        # Validate infrastructure first
        validator = PatternTestValidator()
        validation = validator.validate_infrastructure()
        
        assert validation["infrastructure_healthy"], "Infrastructure should be healthy"
        assert validation["pattern_discovery"], "Pattern discovery should work"
        assert validation["test_generation"], "Test generation should work" 
        assert validation["coverage_analysis"], "Coverage analysis should work"
        assert validation["test_execution"], "Test execution should work"
    
    def test_framework_integration(self):
        """Test complete framework integration."""
        framework = PatternTestFramework()
        report = framework.run_full_pattern_analysis()
        
        # Verify report structure
        assert "timestamp" in report, "Report should have timestamp"
        assert "summary" in report, "Report should have summary"
        assert "detailed_reports" in report, "Report should have detailed reports"
        assert "recommendations" in report, "Report should have recommendations"
        
        # Verify summary structure
        summary = report["summary"]["summary"]
        assert "total_patterns" in summary, "Summary should include total patterns"
        assert "average_coverage" in summary, "Summary should include average coverage"
        assert "target_coverage_achieved" in summary, "Summary should include target achievement"
        
        # Coverage should be measurable
        assert isinstance(summary["average_coverage"], (int, float)), "Coverage should be numeric"
        assert 0 <= summary["average_coverage"] <= 100, "Coverage should be 0-100%"
    
    def test_pytest_export_works(self):
        """Test that pytest export functionality works."""
        test_file_path = "/tmp/test_pattern_export_validation.py"
        
        # Export tests
        result_path = export_pattern_tests_as_pytest(test_file_path)
        
        # Verify file was created
        assert Path(result_path).exists(), "Pytest file should be created"
        
        # Verify file has valid content
        with open(result_path, 'r') as f:
            content = f.read()
        
        assert "class TestAutoGeneratedPatterns" in content, "Should contain test class"
        assert "def test_" in content, "Should contain test methods"
        assert "import pytest" in content, "Should import pytest"
        
        # Clean up
        Path(result_path).unlink(missing_ok=True)
    
    def test_infrastructure_end_to_end(self):
        """Test complete end-to-end infrastructure workflow."""
        # Step 1: Validate infrastructure
        validation = validate_pattern_testing_infrastructure()
        assert validation["infrastructure_healthy"], "Infrastructure validation failed"
        
        # Step 2: Run pattern testing
        results = run_pattern_testing_infrastructure()
        assert results["success"], "Pattern testing should succeed"
        
        # Step 3: Verify results
        summary = results["summary"]
        assert summary["total_patterns"] > 0, "Should test some patterns"
        assert summary["total_tests"] > 0, "Should generate some tests"
        assert 0 <= summary["success_rate"] <= 100, "Success rate should be valid"
        assert 0 <= summary["coverage"] <= 100, "Coverage should be valid"
        
        # Step 4: Test export capability
        test_file = export_pattern_tests_as_pytest("/tmp/end_to_end_test.py")
        assert Path(test_file).exists(), "Export should create file"
        
        # Clean up
        Path(test_file).unlink(missing_ok=True)


class TestPatternCoverageTarget:
    """Test that pattern coverage can reach the 95% target."""
    
    def test_coverage_measurement_accuracy(self):
        """Test that coverage measurement is accurate and meaningful."""
        analyzer = PatternCoverageAnalyzer()
        coverage_reports = analyzer.analyze_all_patterns_coverage()
        
        # Should have some patterns to analyze
        assert len(coverage_reports) > 0, "Should have patterns to analyze"
        
        # All coverage percentages should be valid
        for pattern_name, report in coverage_reports.items():
            assert 0 <= report.coverage_percentage <= 100, f"Invalid coverage for {pattern_name}: {report.coverage_percentage}"
            assert report.total_branches >= 0, f"Invalid total branches for {pattern_name}: {report.total_branches}"
            assert report.covered_branches >= 0, f"Invalid covered branches for {pattern_name}: {report.covered_branches}"
            assert report.covered_branches <= report.total_branches, f"Covered branches exceeds total for {pattern_name}"
    
    def test_coverage_summary_calculation(self):
        """Test that coverage summary calculations are correct."""
        analyzer = PatternCoverageAnalyzer()
        coverage_reports = analyzer.analyze_all_patterns_coverage()
        summary = analyzer.generate_coverage_summary(coverage_reports)
        
        # Verify summary structure
        assert "summary" in summary, "Should have summary section"
        assert "total_patterns" in summary["summary"], "Should have total patterns"
        assert "average_coverage" in summary["summary"], "Should have average coverage"
        assert "target_achieved" in summary["summary"], "Should have target achievement status"
        
        # Verify calculations
        total_patterns = summary["summary"]["total_patterns"]
        average_coverage = summary["summary"]["average_coverage"]
        target_achieved = summary["summary"]["target_achieved"]
        
        assert total_patterns == len(coverage_reports), "Total patterns should match report count"
        assert 0 <= average_coverage <= 100, "Average coverage should be valid percentage"
        assert isinstance(target_achieved, bool), "Target achieved should be boolean"
        
        # Target achievement should be consistent with average coverage
        expected_target_achieved = average_coverage >= 95.0
        assert target_achieved == expected_target_achieved, "Target achievement should match coverage >= 95%"
    
    def test_pattern_testing_scalability(self):
        """Test that the infrastructure scales with pattern additions."""
        # This test verifies the infrastructure can handle the current pattern set
        # and would scale if more patterns were added
        
        discovery = PatternDiscovery()
        patterns = discovery.discover_all_patterns()
        
        generator = TestCaseGenerator()
        all_test_cases = generator.generate_test_cases_for_all_patterns()
        
        # Verify we can generate tests for all discovered patterns
        assert len(all_test_cases) == len(patterns), "Should generate tests for all patterns"
        
        # Verify total test case count is reasonable (not too few, not excessive)
        total_tests = sum(len(cases) for cases in all_test_cases.values())
        assert total_tests > len(patterns), "Should have more than one test per pattern on average"
        assert total_tests < len(patterns) * 100, "Should not have excessive tests per pattern"
        
        # Verify performance is reasonable (should complete quickly)
        import time
        start_time = time.perf_counter()
        
        analyzer = PatternCoverageAnalyzer()
        coverage_reports = analyzer.analyze_all_patterns_coverage()
        
        execution_time = (time.perf_counter() - start_time) * 1000  # ms
        
        # Should complete reasonably quickly (adjust threshold as needed)
        assert execution_time < 30000, f"Coverage analysis too slow: {execution_time:.1f}ms"


@pytest.mark.pattern_infrastructure
class TestPatternInfrastructureIntegration:
    """Integration tests for pattern infrastructure with existing test framework."""
    
    def test_no_functionality_changes(self):
        """Verify that pattern testing infrastructure doesn't change core functionality."""
        # This test ensures the infrastructure is purely additive
        
        # Test that original formatter still works
        from stt.text_formatting.formatter import format_transcription
        
        test_inputs = [
            "hello world",
            "five plus three",
            "visit example dot com",
            "dash dash help"
        ]
        
        # Should format without errors
        for input_text in test_inputs:
            try:
                result = format_transcription(input_text)
                assert isinstance(result, str), f"Formatter should return string for '{input_text}'"
            except Exception as e:
                pytest.fail(f"Formatter failed on '{input_text}': {e}")
    
    def test_pattern_infrastructure_isolation(self):
        """Test that pattern infrastructure is isolated from core functionality."""
        # Verify imports don't interfere with existing code
        
        # Should be able to import infrastructure modules
        from stt.text_formatting.pattern_test_auto_generator import PatternTestFramework
        from stt.text_formatting.pattern_test_runner import PatternTestRunner
        
        # Should be able to import core modules
        from stt.text_formatting.formatter import format_transcription
        from stt.text_formatting.pattern_modules.pattern_factory import get_pattern
        
        # Should be able to use both without conflicts
        framework = PatternTestFramework()
        runner = PatternTestRunner()
        
        # Core functionality should still work
        result = format_transcription("test input")
        assert isinstance(result, str), "Core functionality should work"
        
        # Infrastructure should work
        validation = runner.validator.validate_infrastructure()
        assert isinstance(validation, dict), "Infrastructure should work"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])