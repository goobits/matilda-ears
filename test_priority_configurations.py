#!/usr/bin/env python3
"""
Test different priority configurations to find optimal ordering.

This script tests various priority configurations and reports which
performs best on the test suite.
"""

import subprocess
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.stt.text_formatting.priority_config import (
    PriorityConfiguration, 
    ProcessorType,
    apply_configuration,
    get_current_config
)

# Import processors to apply configurations
from src.stt.text_formatting.processors.mathematical_processor import MathematicalProcessor
from src.stt.text_formatting.processors.measurement_processor import MeasurementProcessor
from src.stt.text_formatting.processors.financial_processor import FinancialProcessor
from src.stt.text_formatting.processors.temporal_processor import TemporalProcessor
from src.stt.text_formatting.processors.basic_numeric_processor import BasicNumericProcessor


def run_tests():
    """Run the test suite and extract results."""
    print("Running tests...")
    result = subprocess.run(
        ["python", "test.py", "tests/unit/text_formatting/", "--summary"],
        capture_output=True,
        text=True
    )
    
    # Parse the output
    output = result.stdout + result.stderr
    
    # Extract key metrics
    passed = 0
    failed = 0
    
    for line in output.split('\n'):
        if 'passed' in line and 'failed' in line:
            # Look for pattern like "111 failed, 274 passed"
            parts = line.split(',')
            for part in parts:
                if 'passed' in part:
                    passed = int(''.join(filter(str.isdigit, part)))
                elif 'failed' in part:
                    failed = int(''.join(filter(str.isdigit, part)))
    
    return {
        'passed': passed,
        'failed': failed,
        'total': passed + failed,
        'pass_rate': passed / (passed + failed) if (passed + failed) > 0 else 0
    }


def apply_config_to_processors(config: PriorityConfiguration):
    """Apply configuration to all processor instances."""
    # Create instances and apply config
    processors = [
        (MathematicalProcessor(), ProcessorType.MATHEMATICAL),
        (MeasurementProcessor(), ProcessorType.MEASUREMENT),
        (FinancialProcessor(), ProcessorType.FINANCIAL),
        (TemporalProcessor(), ProcessorType.TEMPORAL),
        (BasicNumericProcessor(), ProcessorType.BASIC_NUMERIC),
    ]
    
    for processor, proc_type in processors:
        config.apply_to_processor(processor, proc_type)


def test_configuration(config_name: str) -> dict:
    """Test a specific configuration and return results."""
    print(f"\n{'='*60}")
    print(f"Testing configuration: {config_name}")
    print(f"{'='*60}")
    
    # Apply the configuration
    config = apply_configuration(config_name)
    print(config.get_summary())
    
    # Note: In practice, we need to restart/reload the processors
    # For now, we'll document what needs to be done
    print("\nNOTE: Processors need to be reinitialized with new priorities.")
    print("This requires modifying the processor initialization code.")
    
    # Run tests
    results = run_tests()
    
    # Add configuration details
    results['config_name'] = config_name
    results['timestamp'] = datetime.now().isoformat()
    
    return results


def main():
    """Test all configurations and report results."""
    configurations = [
        'A_current',
        'B_specific_to_general',
        'C_domain_first', 
        'D_frequency_based',
        'E_length_based',
    ]
    
    results = []
    baseline_passed = None
    
    print("Priority Configuration Testing")
    print("=" * 60)
    
    for config_name in configurations:
        result = test_configuration(config_name)
        results.append(result)
        
        if baseline_passed is None:
            baseline_passed = result['passed']
            result['improvement'] = 0
        else:
            result['improvement'] = result['passed'] - baseline_passed
        
        print(f"\nResults for {config_name}:")
        print(f"  Passed: {result['passed']}")
        print(f"  Failed: {result['failed']}")
        print(f"  Pass Rate: {result['pass_rate']:.1%}")
        print(f"  Improvement: {result['improvement']:+d}")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    # Sort by pass rate
    sorted_results = sorted(results, key=lambda x: x['passed'], reverse=True)
    
    print("\nConfiguration Rankings:")
    for i, result in enumerate(sorted_results, 1):
        print(f"{i}. {result['config_name']:<25} {result['passed']} passed ({result['pass_rate']:.1%}) {result['improvement']:+d}")
    
    # Save results
    with open('priority_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\nResults saved to priority_test_results.json")
    
    # Find best configuration
    best = sorted_results[0]
    print(f"\nBest configuration: {best['config_name']} with {best['passed']} passing tests")


if __name__ == "__main__":
    main()