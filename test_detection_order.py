#!/usr/bin/env python3
"""
Test different detection ordering by changing the sequence in numeric_detector.py
"""

import re
import subprocess
import json
from pathlib import Path

# Different detection orders to test
DETECTION_ORDERS = {
    'A_current': [
        'self._detect_numerical_entities',
        'self.basic_detector.detect_cardinal_numbers',
        'self.math_processor.detect_entities',
        'self.measurement_processor.detect_entities',
        'self.temporal_detector.detect_time_expressions',
        'self.format_detector.detect_phone_numbers',
        'self.basic_detector.detect_ordinal_numbers',
        'self.temporal_detector.detect_time_relative',
        'self.basic_detector.detect_fractions',
    ],
    
    'B_math_first': [
        'self.math_processor.detect_entities',  # Math first
        'self.basic_detector.detect_ordinal_numbers',  # Ordinals early
        'self.basic_detector.detect_fractions',  # Fractions early
        'self._detect_numerical_entities',
        'self.measurement_processor.detect_entities',
        'self.temporal_detector.detect_time_expressions',
        'self.temporal_detector.detect_time_relative',
        'self.basic_detector.detect_cardinal_numbers',
        'self.format_detector.detect_phone_numbers',
    ],
    
    'C_temporal_first': [
        'self.temporal_detector.detect_time_expressions',  # Time first
        'self.temporal_detector.detect_time_relative',
        'self.measurement_processor.detect_entities',  # Measurements second
        'self._detect_numerical_entities',
        'self.basic_detector.detect_cardinal_numbers',
        'self.basic_detector.detect_ordinal_numbers',
        'self.basic_detector.detect_fractions',
        'self.math_processor.detect_entities',
        'self.format_detector.detect_phone_numbers',
    ],
    
    'D_basic_first': [
        'self.basic_detector.detect_cardinal_numbers',  # Basic numbers first
        'self.basic_detector.detect_ordinal_numbers',
        'self.basic_detector.detect_fractions',
        'self._detect_numerical_entities',
        'self.temporal_detector.detect_time_expressions',
        'self.measurement_processor.detect_entities',
        'self.math_processor.detect_entities',
        'self.temporal_detector.detect_time_relative',
        'self.format_detector.detect_phone_numbers',
    ],
    
    'E_measurement_first': [
        'self.measurement_processor.detect_entities',  # Measurements first
        'self.temporal_detector.detect_time_expressions',
        'self._detect_numerical_entities',
        'self.basic_detector.detect_cardinal_numbers',
        'self.math_processor.detect_entities',
        'self.basic_detector.detect_ordinal_numbers',
        'self.temporal_detector.detect_time_relative',
        'self.basic_detector.detect_fractions',
        'self.format_detector.detect_phone_numbers',
    ],
}


def generate_detection_method(order_list):
    """Generate the detect_numerical_entities method with specified order."""
    method_template = '''    def detect_numerical_entities(self, text: str, entities: list[Entity]) -> list[Entity]:
        """Detect and return numerical entities from the text."""
        numerical_entities: list[Entity] = []

'''
    
    for i, call in enumerate(order_list):
        # Add proper all_entities tracking
        method_template += f'''        # Detection step {i+1}
        all_entities = entities + numerical_entities
        {call}(text, numerical_entities, all_entities)

'''
    
    method_template += '''        # Sort by position
        numerical_entities.sort(key=lambda e: e.start)
        return numerical_entities'''
    
    return method_template


def update_numeric_detector(order_name, order_list):
    """Update numeric_detector.py with new detection order."""
    filepath = Path('/workspace/src/stt/text_formatting/detectors/numeric_detector.py')
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find the detect_numerical_entities method
    method_start = content.find('def detect_numerical_entities(')
    if method_start == -1:
        print("ERROR: Could not find detect_numerical_entities method")
        return False
    
    # Find the end of the method (next def or class)
    method_end = content.find('\n    def ', method_start + 1)
    if method_end == -1:
        method_end = content.find('\nclass ', method_start + 1)
    if method_end == -1:
        method_end = len(content)
    
    # Generate new method
    new_method = generate_detection_method(order_list)
    
    # Calculate proper indentation by finding the line start
    line_start = content.rfind('\n', 0, method_start) + 1
    indent = method_start - line_start
    
    # Add proper indentation to new method
    indented_method = '\n'.join(' ' * indent + line if line else '' 
                                for line in new_method.split('\n'))
    
    # Replace the method
    new_content = content[:line_start] + indented_method + content[method_end:]
    
    # Write back
    with open(filepath, 'w') as f:
        f.write(new_content)
    
    print(f"Updated detection order to: {order_name}")
    return True


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


def main():
    """Test all detection orders."""
    results = []
    baseline_passed = None
    
    print("Testing Different Detection Orders")
    print("=" * 60)
    
    for order_name, order_list in DETECTION_ORDERS.items():
        print(f"\n{'='*60}")
        print(f"Testing order: {order_name}")
        print(f"{'='*60}")
        
        # Apply the detection order
        if not update_numeric_detector(order_name, order_list):
            print(f"Failed to update detection order for {order_name}")
            continue
        
        # Print the order
        print("\nDetection order:")
        for i, detector in enumerate(order_list, 1):
            detector_name = detector.split('.')[-1].replace('detect_', '')
            print(f"  {i}. {detector_name}")
        
        # Run tests
        result = run_tests()
        
        if baseline_passed is None:
            baseline_passed = result['passed']
            result['improvement'] = 0
        else:
            result['improvement'] = result['passed'] - baseline_passed
        
        result['order_name'] = order_name
        results.append(result)
        
        print(f"\nResults: {result['passed']} passed, {result['failed']} failed ({result['pass_rate']:.1%})")
        print(f"Improvement: {result['improvement']:+d}")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    print("\nDetection Order Rankings:")
    sorted_results = sorted(results, key=lambda x: x['passed'], reverse=True)
    
    for i, result in enumerate(sorted_results, 1):
        improvement = result['improvement']
        print(f"{i}. {result['order_name']:<20} {result['passed']} passed ({result['pass_rate']:.1%}) {improvement:+d}")
    
    # Save results
    with open('detection_order_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    best = sorted_results[0]
    print(f"\nBest detection order: {best['order_name']} with {best['passed']} passing tests")
    
    # If best is not current, apply it
    if best['order_name'] != 'A_current' and best['improvement'] > 0:
        print(f"\nApplying best order '{best['order_name']}' permanently...")
        update_numeric_detector(best['order_name'], DETECTION_ORDERS[best['order_name']])


if __name__ == "__main__":
    main()