#!/usr/bin/env python3
"""
Apply priority configuration to all processors.

This script updates the processor priorities based on the selected configuration.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.stt.text_formatting.priority_config import (
    PriorityConfiguration,
    ProcessorType,
    apply_configuration,
    get_current_config
)


def update_processor_file(filepath: Path, processor_type: ProcessorType, config: PriorityConfiguration):
    """Update a processor file with new priorities."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Get priority range
    min_p, max_p = config.get_priority_range(processor_type)
    
    # Find all priority assignments and update them
    import re
    
    # Count how many priority assignments there are
    priority_matches = list(re.finditer(r'priority\s*=\s*(\d+)', content))
    num_priorities = len(priority_matches)
    
    if num_priorities == 0:
        print(f"No priorities found in {filepath.name}")
        return
    
    # Calculate new priorities distributed across the range
    new_priorities = []
    for i in range(num_priorities):
        # Distribute evenly from max to min (highest priority first)
        position_ratio = i / max(1, num_priorities - 1)
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


def main(config_name: str = 'A_current'):
    """Apply a configuration to all processor files."""
    # Load configuration
    config = PriorityConfiguration.from_name(config_name)
    print(f"Applying configuration: {config_name}")
    print(config.get_summary())
    
    # Map of processor files to types
    processor_files = {
        'mathematical_processor.py': ProcessorType.MATHEMATICAL,
        'measurement_processor.py': ProcessorType.MEASUREMENT,
        'financial_processor.py': ProcessorType.FINANCIAL,
        'temporal_processor.py': ProcessorType.TEMPORAL,
        'basic_numeric_processor.py': ProcessorType.BASIC_NUMERIC,
    }
    
    processors_dir = Path(__file__).parent / 'src' / 'stt' / 'text_formatting' / 'processors'
    
    for filename, proc_type in processor_files.items():
        filepath = processors_dir / filename
        if filepath.exists():
            update_processor_file(filepath, proc_type, config)
        else:
            print(f"Warning: {filename} not found")
    
    print(f"\nConfiguration '{config_name}' applied to all processors")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        config_name = sys.argv[1]
    else:
        config_name = 'A_current'
    
    main(config_name)