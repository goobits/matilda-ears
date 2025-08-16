#!/usr/bin/env python3
"""
Time Range Pattern Test Runner

A dedicated script for testing and validating time range pattern behavior
in the text formatting system. This script provides systematic validation
of patterns like "from nine to five" → "From 9 to 5".
"""

import sys
import os
import argparse
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Graceful import handling
try:
    from stt.text_formatting.pattern_integration_tester import create_integration_tester
    from stt.text_formatting.pattern_testing_framework import create_test_framework
    from stt.text_formatting.formatter import format_transcription
    IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import required modules: {e}")
    create_integration_tester = None
    create_test_framework = None
    format_transcription = None
    IMPORTS_AVAILABLE = False


def test_direct_formatter(test_cases):
    """Test cases directly through the formatter."""
    if not IMPORTS_AVAILABLE:
        print("Skipping test - required imports not available")
        return
        
    print("=" * 60)
    print("DIRECT FORMATTER TESTING")
    print("=" * 60)
    
    for i, (input_text, expected) in enumerate(test_cases, 1):
        try:
            output = format_transcription(input_text)
            status = "✅ PASS" if output.strip() == expected.strip() else "❌ FAIL"
            
            print(f"\nTest {i}:")
            print(f"  Input:    '{input_text}'")
            print(f"  Expected: '{expected}'")
            print(f"  Actual:   '{output}'")
            print(f"  Status:   {status}")
            
        except Exception as e:
            print(f"\nTest {i}:")
            print(f"  Input:    '{input_text}'")
            print(f"  Expected: '{expected}'")
            print(f"  Error:    {e}")
            print(f"  Status:   ❌ ERROR")


def test_pattern_framework():
    """Test using the pattern testing framework."""
    print("=" * 60)
    print("PATTERN FRAMEWORK TESTING")
    print("=" * 60)
    
    try:
        tester = create_integration_tester()
        report = tester.test_time_range_patterns()
        
        print(f"\nTime Range Pattern Test Results:")
        print(f"  Category: {report.pattern_category}")
        print(f"  Total tests: {report.test_count}")
        print(f"  Passed: {report.passed_count}")
        print(f"  Failed: {report.failed_count}")
        print(f"  Success rate: {report.success_rate:.1f}%")
        print(f"  Avg execution time: {report.avg_execution_time_ms:.2f}ms")
        
        # Show detailed results for failed tests
        failed_results = [r for r in report.detailed_results if not r.passed]
        if failed_results:
            print(f"\nFailed Test Details:")
            for i, result in enumerate(failed_results, 1):
                print(f"  {i}. Input: '{result.test_case.input_text}'")
                print(f"     Expected: '{result.expected_output}'")
                print(f"     Actual:   '{result.formatter_output}'")
                print(f"     Context:  {result.test_case.context}")
                if result.error_message:
                    print(f"     Error:    {result.error_message}")
                print()
        
        # Show recommendations
        if report.recommendations:
            print(f"Recommendations:")
            for i, rec in enumerate(report.recommendations, 1):
                print(f"  {i}. {rec}")
        
        return report
        
    except Exception as e:
        print(f"Pattern framework testing failed: {e}")
        return None


def test_comprehensive_validation():
    """Run comprehensive validation across all pattern categories."""
    print("=" * 60)
    print("COMPREHENSIVE VALIDATION")
    print("=" * 60)
    
    try:
        tester = create_integration_tester()
        report = tester.generate_comprehensive_validation_report()
        
        # Print summary using the built-in method
        tester.print_summary_report(report)
        
        # Save the report
        output_file = "/tmp/time_range_validation_report.json"
        tester.save_report(report, output_file)
        print(f"\nDetailed report saved to: {output_file}")
        
        return report
        
    except Exception as e:
        print(f"Comprehensive validation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_quick_test():
    """Run a quick test on the target case."""
    print("=" * 60)
    print("QUICK TARGET CASE TEST")
    print("=" * 60)
    
    target_cases = [
        ("from nine to five", "From 9 to 5"),
        ("nine to five", "9–5"),
        ("meeting from two to three", "Meeting from 2 to 3"),
        ("working nine to five shift", "Working 9–5 shift"),
    ]
    
    test_direct_formatter(target_cases)


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description="Test runner for time range patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_time_range_patterns.py --quick
  python test_time_range_patterns.py --framework
  python test_time_range_patterns.py --comprehensive
  python test_time_range_patterns.py --all
        """
    )
    
    parser.add_argument(
        "--quick", action="store_true",
        help="Run quick test on target cases"
    )
    parser.add_argument(
        "--framework", action="store_true",
        help="Test using pattern framework"
    )
    parser.add_argument(
        "--comprehensive", action="store_true",
        help="Run comprehensive validation"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run all tests"
    )
    parser.add_argument(
        "--output", type=str, default="/tmp/pattern_test_results.json",
        help="Output file for detailed results"
    )
    
    args = parser.parse_args()
    
    if not any([args.quick, args.framework, args.comprehensive, args.all]):
        # Default to quick test
        args.quick = True
    
    results = {}
    
    try:
        if args.quick or args.all:
            print("\n" + "=" * 70)
            print("RUNNING QUICK TARGET CASE TEST")
            print("=" * 70)
            run_quick_test()
            results["quick_test_completed"] = True
        
        if args.framework or args.all:
            print("\n" + "=" * 70)
            print("RUNNING PATTERN FRAMEWORK TEST")
            print("=" * 70)
            framework_report = test_pattern_framework()
            results["framework_test"] = framework_report
        
        if args.comprehensive or args.all:
            print("\n" + "=" * 70)
            print("RUNNING COMPREHENSIVE VALIDATION")
            print("=" * 70)
            comprehensive_report = test_comprehensive_validation()
            results["comprehensive_test"] = comprehensive_report
        
        # Final summary
        print("\n" + "=" * 70)
        print("TEST RUNNER SUMMARY")
        print("=" * 70)
        
        if "framework_test" in results and results["framework_test"]:
            report = results["framework_test"]
            print(f"✅ Framework test completed:")
            print(f"   Time range patterns: {report.success_rate:.1f}% success rate")
            print(f"   {report.passed_count}/{report.test_count} tests passed")
        
        if "comprehensive_test" in results and results["comprehensive_test"]:
            report = results["comprehensive_test"]
            summary = report["summary"]
            print(f"✅ Comprehensive test completed:")
            print(f"   Overall success rate: {summary['overall_success_rate']:.1f}%")
            print(f"   {summary['total_passed']}/{summary['total_tests']} tests passed")
            
            # Highlight target case result
            if "target_case_analysis" in report:
                target = report["target_case_analysis"]
                if target.get("found"):
                    status_icon = "✅" if target["status"] == "PASS" else "❌"
                    print(f"   Target case 'from nine to five': {status_icon} {target['status']}")
                    if target["status"] == "FAIL":
                        print(f"   Expected: '{target['expected']}'")
                        print(f"   Actual:   '{target['actual']}'")
        
        print(f"\nFor detailed results, check: {args.output}")
        
    except KeyboardInterrupt:
        print("\n\nTest runner interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest runner failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()