#!/usr/bin/env python3
"""
Update processor priorities based on configuration.
"""

import re
from pathlib import Path

# Priority configurations
CONFIGURATIONS = {
    'A_current': {
        'mathematical': (8, 30),
        'measurement': (15, 25),
        'financial': (10, 20),
        'temporal': (10, 20),
        'basic_numeric': (5, 15),
    },
    
    'B_specific_to_general': {
        'mathematical': (100, 120),
        'financial': (80, 100),
        'temporal': (60, 80),
        'measurement': (40, 60),
        'basic_numeric': (20, 40),
    },
    
    'C_domain_first': {
        'financial': (100, 120),
        'temporal': (80, 100),
        'mathematical': (50, 70),
        'measurement': (40, 60),
        'basic_numeric': (20, 40),
    },
    
    'D_frequency_based': {
        'temporal': (100, 120),
        'measurement': (80, 100),
        'basic_numeric': (70, 90),
        'financial': (60, 80),
        'mathematical': (30, 50),
    },
    
    'E_length_based': {
        'mathematical': (100, 120),
        'temporal': (80, 100),
        'measurement': (60, 80),
        'financial': (40, 60),
        'basic_numeric': (20, 40),
    },
}


def update_processor_file(filepath: Path, min_p: int, max_p: int):
    """Update a processor file with new priorities."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find all priority assignments
    priority_matches = list(re.finditer(r'priority\s*=\s*(\d+)', content))
    num_priorities = len(priority_matches)
    
    if num_priorities == 0:
        print(f"No priorities found in {filepath.name}")
        return
    
    # Calculate new priorities distributed across the range
    new_priorities = []
    for i in range(num_priorities):
        # Distribute evenly from max to min (highest priority first)
        if num_priorities == 1:
            priority = max_p
        else:
            position_ratio = i / (num_priorities - 1)
            priority = max_p - int(position_ratio * (max_p - min_p))
        new_priorities.append(priority)
    
    # Replace priorities in reverse order to maintain positions
    for i, match in enumerate(reversed(priority_matches)):
        old_priority = match.group(1)
        new_priority = new_priorities[-(i+1)]  # Get from end due to reverse
        
        # Replace this specific occurrence
        start, end = match.span(1)
        content = content[:start] + str(new_priority) + content[end:]
    
    # Write back
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Updated {filepath.name}: {num_priorities} priorities set to range {min_p}-{max_p}")


def apply_configuration(config_name: str):
    """Apply a configuration to all processors."""
    if config_name not in CONFIGURATIONS:
        print(f"Unknown configuration: {config_name}")
        return
    
    config = CONFIGURATIONS[config_name]
    print(f"\nApplying configuration: {config_name}")
    print("Priority ranges:")
    for proc_type, (min_p, max_p) in sorted(config.items(), key=lambda x: x[1][1], reverse=True):
        print(f"  {proc_type:<15} {min_p:3d} - {max_p:3d}")
    
    # Map of processor files
    processor_files = {
        'mathematical_processor.py': 'mathematical',
        'measurement_processor.py': 'measurement',
        'financial_processor.py': 'financial',
        'temporal_processor.py': 'temporal',
        'basic_numeric_processor.py': 'basic_numeric',
    }
    
    processors_dir = Path('/workspace/src/stt/text_formatting/processors')
    
    for filename, proc_type in processor_files.items():
        filepath = processors_dir / filename
        if filepath.exists() and proc_type in config:
            min_p, max_p = config[proc_type]
            update_processor_file(filepath, min_p, max_p)
        elif not filepath.exists():
            print(f"Warning: {filename} not found")
    
    print(f"\nConfiguration '{config_name}' applied successfully")


def main():
    """Test all configurations."""
    import subprocess
    import json
    
    results = []
    
    for config_name in ['A_current', 'B_specific_to_general', 'C_domain_first', 
                       'D_frequency_based', 'E_length_based']:
        
        print(f"\n{'='*60}")
        print(f"Testing configuration: {config_name}")
        print(f"{'='*60}")
        
        # Apply configuration
        apply_configuration(config_name)
        
        # Run tests
        print("\nRunning tests...")
        result = subprocess.run(
            ["python", "test.py", "tests/unit/text_formatting/", "--summary"],
            capture_output=True,
            text=True
        )
        
        # Parse results
        output = result.stdout + result.stderr
        passed = 0
        failed = 0
        
        for line in output.split('\n'):
            if 'passed' in line and 'failed' in line:
                parts = line.split(',')
                for part in parts:
                    if 'passed' in part:
                        passed = int(''.join(filter(str.isdigit, part)))
                    elif 'failed' in part:
                        failed = int(''.join(filter(str.isdigit, part)))
        
        results.append({
            'config': config_name,
            'passed': passed,
            'failed': failed,
            'total': passed + failed,
            'pass_rate': passed / (passed + failed) if (passed + failed) > 0 else 0
        })
        
        print(f"\nResults: {passed} passed, {failed} failed ({passed/(passed+failed)*100:.1f}%)")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    print("\nConfiguration Rankings:")
    sorted_results = sorted(results, key=lambda x: x['passed'], reverse=True)
    baseline = results[0]['passed']
    
    for i, result in enumerate(sorted_results, 1):
        improvement = result['passed'] - baseline
        print(f"{i}. {result['config']:<25} {result['passed']} passed ({result['pass_rate']:.1%}) {improvement:+d}")
    
    # Save results
    with open('priority_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    best = sorted_results[0]
    print(f"\nBest configuration: {best['config']} with {best['passed']} passing tests")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # Apply single configuration
        apply_configuration(sys.argv[1])
    else:
        # Test all configurations
        main()