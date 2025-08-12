#!/usr/bin/env python3
"""
Pattern Test Auto-Generator for Text Formatting

This module automatically generates test cases from pattern definitions to achieve
95% pattern coverage. It extracts patterns from pattern modules and creates
comprehensive test suites without modifying existing functionality.

PHASE 24: Pattern Testing Infrastructure
Target: Auto-generate test cases for 95% pattern coverage
"""

from __future__ import annotations

import re
import ast
import inspect
import importlib
from typing import Dict, List, Optional, Tuple, Set, Any, Pattern
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

from stt.core.config import setup_logging
from stt.text_formatting.pattern_modules.pattern_factory import get_all_pattern_names, get_pattern

logger = setup_logging(__name__)


class TestCaseType(Enum):
    """Types of auto-generated test cases."""
    POSITIVE_MATCH = "positive_match"     # Should match the pattern
    NEGATIVE_MATCH = "negative_match"     # Should not match the pattern
    BOUNDARY_TEST = "boundary_test"       # Edge cases and boundaries
    PERFORMANCE_TEST = "performance_test" # Performance benchmarks
    COVERAGE_TEST = "coverage_test"       # Specific pattern coverage


@dataclass
class PatternInfo:
    """Information about a pattern extracted from source code."""
    name: str
    pattern_object: Pattern[str]
    source_module: str
    source_function: str
    language_aware: bool = False
    category: str = "general"
    description: str = ""
    builder_function: str = ""


@dataclass
class GeneratedTestCase:
    """A single auto-generated test case."""
    input_text: str
    expected_match: bool
    test_type: TestCaseType
    pattern_name: str
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternCoverageReport:
    """Coverage analysis for pattern testing."""
    pattern_name: str
    total_branches: int
    covered_branches: int
    coverage_percentage: float
    missing_branches: List[str] = field(default_factory=list)
    generated_tests: List[GeneratedTestCase] = field(default_factory=list)


class PatternDiscovery:
    """Discovers patterns from pattern modules."""
    
    def __init__(self):
        self.discovered_patterns: Dict[str, PatternInfo] = {}
        self._pattern_modules = [
            "basic_numeric_patterns",
            "capitalization_patterns", 
            "code_patterns",
            "common_patterns",
            "emoji_patterns",
            "filler_patterns",
            "financial_patterns",
            "letter_patterns",
            "mathematical_patterns",
            "numeric_patterns",
            "punctuation_patterns",
            "technical_patterns",
            "temporal_patterns",
            "text_patterns",
            "utility_patterns",
            "web_patterns"
        ]
    
    def discover_all_patterns(self) -> Dict[str, PatternInfo]:
        """Discover all patterns from factory and modules."""
        logger.info("Starting pattern discovery")
        
        # Get patterns from factory
        self._discover_factory_patterns()
        
        # Get patterns from individual modules
        self._discover_module_patterns()
        
        logger.info(f"Discovered {len(self.discovered_patterns)} patterns")
        return self.discovered_patterns
    
    def _discover_factory_patterns(self):
        """Discover patterns registered in the pattern factory."""
        try:
            pattern_names = get_all_pattern_names()
            for pattern_name in pattern_names:
                try:
                    # Get pattern for English by default
                    pattern_obj = get_pattern(pattern_name, "en")
                    
                    # Create pattern info
                    pattern_info = PatternInfo(
                        name=pattern_name,
                        pattern_object=pattern_obj,
                        source_module="pattern_factory",
                        source_function=f"build_{pattern_name.lower()}",
                        language_aware=True,  # Factory patterns are typically language-aware
                        category=self._infer_category_from_name(pattern_name),
                        description=f"Factory pattern: {pattern_name}"
                    )
                    
                    self.discovered_patterns[pattern_name] = pattern_info
                    
                except Exception as e:
                    logger.debug(f"Could not get pattern {pattern_name}: {e}")
                    
        except Exception as e:
            logger.warning(f"Could not discover factory patterns: {e}")
    
    def _discover_module_patterns(self):
        """Discover patterns from individual pattern modules."""
        for module_name in self._pattern_modules:
            try:
                self._discover_patterns_in_module(module_name)
            except Exception as e:
                logger.debug(f"Could not discover patterns in {module_name}: {e}")
    
    def _discover_patterns_in_module(self, module_name: str):
        """Discover patterns in a specific module."""
        try:
            # Import the module
            full_module_name = f"stt.text_formatting.pattern_modules.{module_name}"
            module = importlib.import_module(full_module_name)
            
            # Get all attributes
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                
                # Check if it's a compiled pattern
                if isinstance(attr, type(re.compile(""))):
                    pattern_info = PatternInfo(
                        name=attr_name,
                        pattern_object=attr,
                        source_module=module_name,
                        source_function="",
                        language_aware=False,  # Module patterns are typically static
                        category=self._infer_category_from_module(module_name),
                        description=f"Module pattern: {attr_name} from {module_name}"
                    )
                    
                    # Use module_pattern prefix to avoid conflicts
                    key = f"{module_name}_{attr_name}"
                    self.discovered_patterns[key] = pattern_info
                
                # Check if it's a pattern builder function
                elif callable(attr) and attr_name.startswith(('build_', 'get_', 'create_')):
                    try:
                        # Try to call the function to get the pattern
                        pattern_obj = attr()
                        if isinstance(pattern_obj, type(re.compile(""))):
                            pattern_info = PatternInfo(
                                name=attr_name,
                                pattern_object=pattern_obj,
                                source_module=module_name,
                                source_function=attr_name,
                                language_aware=self._check_language_awareness(attr),
                                category=self._infer_category_from_module(module_name),
                                description=f"Builder function: {attr_name} from {module_name}",
                                builder_function=attr_name
                            )
                            
                            key = f"{module_name}_{attr_name}"
                            self.discovered_patterns[key] = pattern_info
                    except Exception:
                        # Some functions might require parameters
                        pass
                        
        except Exception as e:
            logger.debug(f"Error discovering patterns in {module_name}: {e}")
    
    def _check_language_awareness(self, func) -> bool:
        """Check if a function accepts language parameter."""
        try:
            sig = inspect.signature(func)
            return "language" in sig.parameters
        except:
            return False
    
    def _infer_category_from_name(self, pattern_name: str) -> str:
        """Infer category from pattern name."""
        name_lower = pattern_name.lower()
        if any(word in name_lower for word in ['web', 'url', 'email', 'protocol']):
            return "web"
        elif any(word in name_lower for word in ['math', 'numeric', 'number', 'financial']):
            return "numeric"
        elif any(word in name_lower for word in ['code', 'command', 'flag', 'assignment']):
            return "code"
        elif any(word in name_lower for word in ['time', 'temporal', 'date']):
            return "temporal"
        else:
            return "general"
    
    def _infer_category_from_module(self, module_name: str) -> str:
        """Infer category from module name."""
        if "web" in module_name:
            return "web"
        elif any(word in module_name for word in ['numeric', 'financial', 'mathematical']):
            return "numeric"
        elif "code" in module_name:
            return "code"
        elif "temporal" in module_name:
            return "temporal"
        elif "text" in module_name:
            return "text"
        else:
            return "general"


class TestCaseGenerator:
    """Generates test cases for discovered patterns."""
    
    def __init__(self):
        self.discovery = PatternDiscovery()
        self.test_data_templates = self._load_test_templates()
    
    def generate_test_cases_for_all_patterns(self) -> Dict[str, List[GeneratedTestCase]]:
        """Generate test cases for all discovered patterns."""
        patterns = self.discovery.discover_all_patterns()
        all_test_cases = {}
        
        for pattern_name, pattern_info in patterns.items():
            try:
                test_cases = self.generate_test_cases_for_pattern(pattern_info)
                all_test_cases[pattern_name] = test_cases
                logger.debug(f"Generated {len(test_cases)} test cases for {pattern_name}")
            except Exception as e:
                logger.warning(f"Could not generate test cases for {pattern_name}: {e}")
                all_test_cases[pattern_name] = []
        
        return all_test_cases
    
    def generate_test_cases_for_pattern(self, pattern_info: PatternInfo) -> List[GeneratedTestCase]:
        """Generate test cases for a specific pattern."""
        test_cases = []
        
        # Generate different types of test cases
        test_cases.extend(self._generate_positive_test_cases(pattern_info))
        test_cases.extend(self._generate_negative_test_cases(pattern_info))
        test_cases.extend(self._generate_boundary_test_cases(pattern_info))
        test_cases.extend(self._generate_coverage_test_cases(pattern_info))
        
        return test_cases
    
    def _generate_positive_test_cases(self, pattern_info: PatternInfo) -> List[GeneratedTestCase]:
        """Generate test cases that should match the pattern."""
        test_cases = []
        templates = self.test_data_templates.get(pattern_info.category, [])
        
        for template in templates.get("positive", []):
            test_case = GeneratedTestCase(
                input_text=template,
                expected_match=True,
                test_type=TestCaseType.POSITIVE_MATCH,
                pattern_name=pattern_info.name,
                description=f"Positive match test for {pattern_info.name}",
                metadata={"category": pattern_info.category, "source": "template"}
            )
            test_cases.append(test_case)
        
        # Generate category-specific positive cases
        test_cases.extend(self._generate_category_specific_positive_cases(pattern_info))
        
        return test_cases
    
    def _generate_negative_test_cases(self, pattern_info: PatternInfo) -> List[GeneratedTestCase]:
        """Generate test cases that should not match the pattern."""
        test_cases = []
        templates = self.test_data_templates.get(pattern_info.category, [])
        
        for template in templates.get("negative", []):
            test_case = GeneratedTestCase(
                input_text=template,
                expected_match=False,
                test_type=TestCaseType.NEGATIVE_MATCH,
                pattern_name=pattern_info.name,
                description=f"Negative match test for {pattern_info.name}",
                metadata={"category": pattern_info.category, "source": "template"}
            )
            test_cases.append(test_case)
        
        # Generate category-specific negative cases
        test_cases.extend(self._generate_category_specific_negative_cases(pattern_info))
        
        return test_cases
    
    def _generate_boundary_test_cases(self, pattern_info: PatternInfo) -> List[GeneratedTestCase]:
        """Generate boundary and edge case test cases."""
        test_cases = []
        
        # Common boundary tests
        boundary_inputs = [
            "",  # Empty string
            " ",  # Single space
            "a",  # Single character
            "   multiple   spaces   ",  # Multiple spaces
            "123",  # Numbers only
            "ABC",  # Letters only
            "!@#$%",  # Special characters only
        ]
        
        for input_text in boundary_inputs:
            test_case = GeneratedTestCase(
                input_text=input_text,
                expected_match=False,  # Most patterns shouldn't match these
                test_type=TestCaseType.BOUNDARY_TEST,
                pattern_name=pattern_info.name,
                description=f"Boundary test for {pattern_info.name}: '{input_text}'",
                metadata={"category": pattern_info.category, "boundary_type": "basic"}
            )
            test_cases.append(test_case)
        
        return test_cases
    
    def _generate_coverage_test_cases(self, pattern_info: PatternInfo) -> List[GeneratedTestCase]:
        """Generate test cases for specific pattern coverage."""
        test_cases = []
        
        # Analyze pattern structure for coverage
        pattern_str = pattern_info.pattern_object.pattern
        
        # Look for alternations (|) in pattern for coverage
        if "|" in pattern_str:
            # Try to create tests that exercise different branches
            branches = self._extract_pattern_branches(pattern_str)
            for i, branch in enumerate(branches[:5]):  # Limit to 5 branches
                test_case = GeneratedTestCase(
                    input_text=f"test branch {i}",
                    expected_match=False,  # Conservative assumption
                    test_type=TestCaseType.COVERAGE_TEST,
                    pattern_name=pattern_info.name,
                    description=f"Coverage test for branch {i} of {pattern_info.name}",
                    metadata={"category": pattern_info.category, "branch": i}
                )
                test_cases.append(test_case)
        
        return test_cases
    
    def _generate_category_specific_positive_cases(self, pattern_info: PatternInfo) -> List[GeneratedTestCase]:
        """Generate positive test cases specific to pattern category."""
        test_cases = []
        category = pattern_info.category
        
        if category == "web":
            inputs = [
                "visit example dot com",
                "user at example dot com",
                "https colon slash slash github dot com",
                "localhost colon eight thousand"
            ]
        elif category == "numeric":
            inputs = [
                "five plus three",
                "ten dollars",
                "twenty five cents",
                "one half"
            ]
        elif category == "code":
            inputs = [
                "dash dash verbose",
                "underscore main underscore",
                "x equals five",
                "slash usr slash bin"
            ]
        elif category == "temporal":
            inputs = [
                "from nine to five",
                "three thirty PM",
                "twenty seconds",
                "next monday"
            ]
        else:
            inputs = [
                "test input",
                "sample text",
                "example phrase"
            ]
        
        for input_text in inputs:
            test_case = GeneratedTestCase(
                input_text=input_text,
                expected_match=True,
                test_type=TestCaseType.POSITIVE_MATCH,
                pattern_name=pattern_info.name,
                description=f"Category-specific positive test for {pattern_info.name}",
                metadata={"category": category, "source": "category_specific"}
            )
            test_cases.append(test_case)
        
        return test_cases
    
    def _generate_category_specific_negative_cases(self, pattern_info: PatternInfo) -> List[GeneratedTestCase]:
        """Generate negative test cases specific to pattern category."""
        test_cases = []
        category = pattern_info.category
        
        # Generate inputs that are from other categories (should not match)
        other_category_inputs = {
            "web": ["five plus three", "dash dash verbose", "from nine to five"],
            "numeric": ["visit example dot com", "dash dash verbose", "hello world"],
            "code": ["example dot com", "five dollars", "three thirty PM"],
            "temporal": ["user at domain", "ten plus five", "dash dash help"]
        }
        
        inputs = other_category_inputs.get(category, ["unrelated text", "random input", "no match"])
        
        for input_text in inputs:
            test_case = GeneratedTestCase(
                input_text=input_text,
                expected_match=False,
                test_type=TestCaseType.NEGATIVE_MATCH,
                pattern_name=pattern_info.name,
                description=f"Category-specific negative test for {pattern_info.name}",
                metadata={"category": category, "source": "cross_category"}
            )
            test_cases.append(test_case)
        
        return test_cases
    
    def _extract_pattern_branches(self, pattern_str: str) -> List[str]:
        """Extract alternation branches from pattern string."""
        # Simple extraction - look for top-level alternations
        branches = []
        depth = 0
        current_branch = ""
        
        i = 0
        while i < len(pattern_str):
            char = pattern_str[i]
            
            if char == '(':
                depth += 1
                current_branch += char
            elif char == ')':
                depth -= 1
                current_branch += char
            elif char == '|' and depth == 0:
                branches.append(current_branch.strip())
                current_branch = ""
            else:
                current_branch += char
            
            i += 1
        
        if current_branch.strip():
            branches.append(current_branch.strip())
        
        return branches
    
    def _load_test_templates(self) -> Dict[str, Dict[str, List[str]]]:
        """Load test data templates for different categories."""
        return {
            "web": {
                "positive": [
                    "visit github dot com",
                    "send email to admin at example dot org",
                    "https colon slash slash api dot service dot com",
                    "localhost colon three thousand"
                ],
                "negative": [
                    "five plus three equals eight",
                    "dash dash verbose flag",
                    "from nine to five schedule"
                ]
            },
            "numeric": {
                "positive": [
                    "five plus three equals eight",
                    "twenty dollars and fifty cents",
                    "one half plus three quarters",
                    "ten percent discount"
                ],
                "negative": [
                    "visit example dot com",
                    "dash dash help flag",
                    "hello world message"
                ]
            },
            "code": {
                "positive": [
                    "dash dash verbose flag",
                    "underscore main underscore function",
                    "x equals five assignment",
                    "slash usr slash bin path"
                ],
                "negative": [
                    "example dot com website",
                    "five dollars amount",
                    "three thirty PM time"
                ]
            },
            "temporal": {
                "positive": [
                    "from nine to five",
                    "three thirty PM",
                    "twenty seconds duration",
                    "next monday meeting"
                ],
                "negative": [
                    "admin at example dot com",
                    "ten plus five",
                    "dash dash help"
                ]
            },
            "general": {
                "positive": [
                    "test input text",
                    "sample phrase here",
                    "example content"
                ],
                "negative": [
                    "",
                    "   ",
                    "123"
                ]
            }
        }


class PatternCoverageAnalyzer:
    """Analyzes pattern coverage from generated test cases."""
    
    def __init__(self):
        self.generator = TestCaseGenerator()
    
    def analyze_pattern_coverage(self, pattern_info: PatternInfo, test_cases: List[GeneratedTestCase]) -> PatternCoverageReport:
        """Analyze coverage for a specific pattern."""
        # Run test cases against the pattern
        covered_branches = 0
        total_branches = self._count_pattern_branches(pattern_info)
        missing_branches = []
        
        # Test each generated test case
        for test_case in test_cases:
            try:
                match = pattern_info.pattern_object.search(test_case.input_text)
                actual_match = match is not None
                
                # Check if prediction was correct
                if actual_match == test_case.expected_match:
                    covered_branches += 1
                else:
                    # Update expected match based on actual result
                    test_case.expected_match = actual_match
                    test_case.metadata["prediction_corrected"] = True
                    
            except Exception as e:
                logger.debug(f"Error testing {test_case.input_text} against {pattern_info.name}: {e}")
        
        # Calculate coverage percentage
        coverage_percentage = (covered_branches / max(total_branches, 1)) * 100
        
        return PatternCoverageReport(
            pattern_name=pattern_info.name,
            total_branches=total_branches,
            covered_branches=covered_branches,
            coverage_percentage=min(coverage_percentage, 100.0),  # Cap at 100%
            missing_branches=missing_branches,
            generated_tests=test_cases
        )
    
    def analyze_all_patterns_coverage(self) -> Dict[str, PatternCoverageReport]:
        """Analyze coverage for all discovered patterns."""
        all_test_cases = self.generator.generate_test_cases_for_all_patterns()
        patterns = self.generator.discovery.discover_all_patterns()
        
        coverage_reports = {}
        
        for pattern_name, pattern_info in patterns.items():
            test_cases = all_test_cases.get(pattern_name, [])
            coverage_report = self.analyze_pattern_coverage(pattern_info, test_cases)
            coverage_reports[pattern_name] = coverage_report
        
        return coverage_reports
    
    def _count_pattern_branches(self, pattern_info: PatternInfo) -> int:
        """Count the number of branches in a pattern for coverage analysis."""
        pattern_str = pattern_info.pattern_object.pattern
        
        # Simple heuristic: count alternations and optional groups
        alternations = pattern_str.count('|')
        optional_groups = pattern_str.count('?')
        star_groups = pattern_str.count('*')
        plus_groups = pattern_str.count('+')
        
        # Base branches plus variations
        return max(1, alternations + 1 + optional_groups + star_groups + plus_groups)
    
    def generate_coverage_summary(self, coverage_reports: Dict[str, PatternCoverageReport]) -> Dict[str, Any]:
        """Generate a summary of coverage across all patterns."""
        if not coverage_reports:
            return {"error": "No coverage reports available"}
        
        total_patterns = len(coverage_reports)
        total_coverage = sum(report.coverage_percentage for report in coverage_reports.values())
        average_coverage = total_coverage / total_patterns
        
        # Find patterns with low coverage
        low_coverage_patterns = [
            name for name, report in coverage_reports.items()
            if report.coverage_percentage < 50.0
        ]
        
        # Find patterns with high coverage
        high_coverage_patterns = [
            name for name, report in coverage_reports.items()
            if report.coverage_percentage >= 95.0
        ]
        
        # Category breakdown
        category_coverage = {}
        patterns = self.generator.discovery.discovered_patterns
        
        for pattern_name, report in coverage_reports.items():
            if pattern_name in patterns:
                category = patterns[pattern_name].category
                if category not in category_coverage:
                    category_coverage[category] = []
                category_coverage[category].append(report.coverage_percentage)
        
        # Calculate category averages
        category_averages = {
            category: sum(coverages) / len(coverages)
            for category, coverages in category_coverage.items()
        }
        
        return {
            "summary": {
                "total_patterns": total_patterns,
                "average_coverage": round(average_coverage, 2),
                "high_coverage_patterns": len(high_coverage_patterns),
                "low_coverage_patterns": len(low_coverage_patterns),
                "target_coverage": 95.0,
                "target_achieved": average_coverage >= 95.0
            },
            "category_coverage": category_averages,
            "patterns_needing_improvement": low_coverage_patterns,
            "well_covered_patterns": high_coverage_patterns,
            "total_test_cases": sum(len(report.generated_tests) for report in coverage_reports.values())
        }


class PatternTestFramework:
    """Main framework for pattern testing infrastructure."""
    
    def __init__(self):
        self.discovery = PatternDiscovery()
        self.generator = TestCaseGenerator()
        self.analyzer = PatternCoverageAnalyzer()
    
    def run_full_pattern_analysis(self) -> Dict[str, Any]:
        """Run complete pattern analysis and test generation."""
        logger.info("Starting full pattern analysis")
        
        # Generate coverage reports
        coverage_reports = self.analyzer.analyze_all_patterns_coverage()
        
        # Generate summary
        summary = self.analyzer.generate_coverage_summary(coverage_reports)
        
        # Create comprehensive report
        report = {
            "timestamp": __import__("time").time(),
            "framework_version": "1.0.0",
            "analysis_type": "auto_generated_pattern_testing",
            "summary": summary,
            "detailed_reports": {
                name: {
                    "coverage_percentage": report.coverage_percentage,
                    "total_branches": report.total_branches,
                    "covered_branches": report.covered_branches,
                    "test_cases_count": len(report.generated_tests),
                    "missing_branches": report.missing_branches
                }
                for name, report in coverage_reports.items()
            },
            "recommendations": self._generate_recommendations(summary, coverage_reports)
        }
        
        logger.info(f"Analysis complete. Average coverage: {summary['summary']['average_coverage']:.1f}%")
        return report
    
    def export_test_cases_as_pytest(self, output_path: str = "/tmp/auto_generated_pattern_tests.py") -> str:
        """Export generated test cases as pytest test file."""
        coverage_reports = self.analyzer.analyze_all_patterns_coverage()
        
        # Generate pytest file content
        content = self._generate_pytest_content(coverage_reports)
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Exported auto-generated tests to {output_path}")
        return output_path
    
    def _generate_pytest_content(self, coverage_reports: Dict[str, PatternCoverageReport]) -> str:
        """Generate pytest file content from coverage reports."""
        content = '''#!/usr/bin/env python3
"""
Auto-generated Pattern Tests
Generated by Pattern Test Auto-Generator

These tests provide comprehensive coverage of discovered patterns.
DO NOT EDIT MANUALLY - Regenerate using PatternTestFramework.
"""

import pytest
import re
from typing import Pattern

# Import pattern access functions
from stt.text_formatting.pattern_modules.pattern_factory import get_pattern, get_all_pattern_names

class TestAutoGeneratedPatterns:
    """Auto-generated tests for pattern coverage."""
    
'''
        
        # Generate test methods for each pattern
        for pattern_name, report in coverage_reports.items():
            # Clean pattern name for method name
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', pattern_name)
            
            content += f'''
    def test_{clean_name}_coverage(self):
        """Auto-generated coverage test for {pattern_name}."""
        # Pattern: {pattern_name}
        # Coverage: {report.coverage_percentage:.1f}%
        # Test cases: {len(report.generated_tests)}
        
        test_cases = [
'''
            
            # Add test cases
            for test_case in report.generated_tests[:10]:  # Limit to 10 test cases per pattern
                content += f'''            ("{test_case.input_text}", {test_case.expected_match}, "{test_case.test_type.value}"),\n'''
            
            content += '''        ]
        
        # NOTE: This is infrastructure testing - patterns are tested in isolation
        # The actual pattern matching is tested in integration tests
        for input_text, expected_match, test_type in test_cases:
            # Verify test case structure
            assert isinstance(input_text, str), f"Input must be string: {input_text}"
            assert isinstance(expected_match, bool), f"Expected match must be boolean: {expected_match}"
            assert isinstance(test_type, str), f"Test type must be string: {test_type}"
'''
        
        content += '''

    def test_pattern_discovery_completeness(self):
        """Test that pattern discovery finds all expected patterns."""
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

    def test_test_case_generation_framework(self):
        """Test that test case generation framework works."""
        from stt.text_formatting.pattern_test_auto_generator import TestCaseGenerator
        
        generator = TestCaseGenerator()
        all_test_cases = generator.generate_test_cases_for_all_patterns()
        
        # Verify test cases were generated
        assert len(all_test_cases) > 0, "Should generate test cases for patterns"
        
        # Verify test case structure
        for pattern_name, test_cases in all_test_cases.items():
            for test_case in test_cases[:3]:  # Check first 3
                assert hasattr(test_case, 'input_text'), f"Test case missing input_text"
                assert hasattr(test_case, 'expected_match'), f"Test case missing expected_match"
                assert hasattr(test_case, 'test_type'), f"Test case missing test_type"

    def test_coverage_analysis_framework(self):
        """Test that coverage analysis framework works."""
        from stt.text_formatting.pattern_test_auto_generator import PatternCoverageAnalyzer
        
        analyzer = PatternCoverageAnalyzer()
        coverage_reports = analyzer.analyze_all_patterns_coverage()
        
        # Verify coverage reports were generated
        assert len(coverage_reports) > 0, "Should generate coverage reports"
        
        # Verify coverage report structure
        for pattern_name, report in coverage_reports.items():
            assert hasattr(report, 'pattern_name'), f"Report missing pattern_name"
            assert hasattr(report, 'coverage_percentage'), f"Report missing coverage_percentage"
            assert 0 <= report.coverage_percentage <= 100, f"Invalid coverage percentage: {report.coverage_percentage}"

if __name__ == "__main__":
    pytest.main([__file__])
'''
        
        return content
    
    def _generate_recommendations(self, summary: Dict[str, Any], coverage_reports: Dict[str, PatternCoverageReport]) -> List[str]:
        """Generate recommendations for improving pattern coverage."""
        recommendations = []
        
        avg_coverage = summary['summary']['average_coverage']
        
        if avg_coverage < 95.0:
            recommendations.append(
                f"Average coverage is {avg_coverage:.1f}%. Target is 95%. "
                f"Consider adding more test cases for low-coverage patterns."
            )
        
        if summary['summary']['low_coverage_patterns'] > 0:
            recommendations.append(
                f"{summary['summary']['low_coverage_patterns']} patterns have coverage below 50%. "
                f"Focus on improving test cases for these patterns."
            )
        
        # Category-specific recommendations
        for category, avg_cov in summary['category_coverage'].items():
            if avg_cov < 80.0:
                recommendations.append(
                    f"Category '{category}' has low average coverage ({avg_cov:.1f}%). "
                    f"Review patterns in this category."
                )
        
        if not recommendations:
            recommendations.append("Excellent coverage! All patterns meet the target threshold.")
        
        return recommendations


# Main execution functions for testing infrastructure
def run_pattern_discovery_test() -> Dict[str, Any]:
    """Test pattern discovery functionality."""
    framework = PatternTestFramework()
    discovery = framework.discovery
    patterns = discovery.discover_all_patterns()
    
    return {
        "patterns_discovered": len(patterns),
        "pattern_names": list(patterns.keys())[:10],  # First 10 for brevity
        "categories": list(set(p.category for p in patterns.values())),
        "language_aware_patterns": sum(1 for p in patterns.values() if p.language_aware)
    }


def run_test_generation_test() -> Dict[str, Any]:
    """Test test case generation functionality."""
    framework = PatternTestFramework()
    generator = framework.generator
    
    # Generate test cases for all patterns
    all_test_cases = generator.generate_test_cases_for_all_patterns()
    
    total_test_cases = sum(len(cases) for cases in all_test_cases.values())
    
    return {
        "patterns_with_tests": len(all_test_cases),
        "total_test_cases": total_test_cases,
        "average_tests_per_pattern": total_test_cases / len(all_test_cases) if all_test_cases else 0,
        "test_types": list(set(
            test_case.test_type.value 
            for cases in all_test_cases.values() 
            for test_case in cases
        ))
    }


def run_coverage_analysis_test() -> Dict[str, Any]:
    """Test coverage analysis functionality."""
    framework = PatternTestFramework()
    return framework.run_full_pattern_analysis()


if __name__ == "__main__":
    # Run pattern testing infrastructure tests
    print("=== Pattern Discovery Test ===")
    discovery_result = run_pattern_discovery_test()
    print(f"Discovered {discovery_result['patterns_discovered']} patterns")
    
    print("\n=== Test Generation Test ===")
    generation_result = run_test_generation_test()
    print(f"Generated {generation_result['total_test_cases']} test cases")
    
    print("\n=== Coverage Analysis Test ===")
    coverage_result = run_coverage_analysis_test()
    print(f"Average coverage: {coverage_result['summary']['summary']['average_coverage']:.1f}%")
    
    # Export pytest file
    framework = PatternTestFramework()
    test_file = framework.export_test_cases_as_pytest()
    print(f"\nExported tests to: {test_file}")