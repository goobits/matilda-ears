"""
Priority configuration system for entity processors.

This module provides a language-agnostic priority configuration system
that allows different priority orderings to be tested and optimized.
"""

from enum import Enum
from typing import Dict, Tuple, Optional
import json
from pathlib import Path

from stt.core.config import setup_logging

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


class ProcessorType(Enum):
    """Types of entity processors."""
    MATHEMATICAL = "mathematical"
    FINANCIAL = "financial"
    TEMPORAL = "temporal"
    MEASUREMENT = "measurement"
    BASIC_NUMERIC = "basic_numeric"
    WEB = "web"
    CODE = "code"
    TEXT = "text"


class PriorityConfiguration:
    """Language-agnostic priority configuration for entity processors."""
    
    # Default configuration (current state)
    DEFAULT_CONFIG = {
        ProcessorType.MATHEMATICAL: (8, 30),
        ProcessorType.MEASUREMENT: (15, 25),
        ProcessorType.FINANCIAL: (10, 20),
        ProcessorType.TEMPORAL: (10, 20),
        ProcessorType.BASIC_NUMERIC: (5, 15),
        ProcessorType.WEB: (30, 40),
        ProcessorType.CODE: (25, 35),
        ProcessorType.TEXT: (0, 10),
    }
    
    # Predefined test configurations
    CONFIGURATIONS = {
        'A_current': DEFAULT_CONFIG,
        
        'B_specific_to_general': {
            ProcessorType.MATHEMATICAL: (100, 120),  # Most specific
            ProcessorType.FINANCIAL: (80, 100),
            ProcessorType.TEMPORAL: (60, 80),
            ProcessorType.MEASUREMENT: (40, 60),
            ProcessorType.CODE: (35, 55),
            ProcessorType.WEB: (30, 50),
            ProcessorType.BASIC_NUMERIC: (20, 40),
            ProcessorType.TEXT: (0, 20),
        },
        
        'C_domain_first': {
            ProcessorType.FINANCIAL: (100, 120),     # Domain-specific first
            ProcessorType.TEMPORAL: (80, 100),
            ProcessorType.CODE: (70, 90),
            ProcessorType.WEB: (60, 80),
            ProcessorType.MATHEMATICAL: (50, 70),
            ProcessorType.MEASUREMENT: (40, 60),
            ProcessorType.BASIC_NUMERIC: (20, 40),
            ProcessorType.TEXT: (0, 20),
        },
        
        'D_frequency_based': {
            ProcessorType.TEMPORAL: (100, 120),      # Most common in speech
            ProcessorType.MEASUREMENT: (80, 100),
            ProcessorType.BASIC_NUMERIC: (70, 90),
            ProcessorType.FINANCIAL: (60, 80),
            ProcessorType.TEXT: (50, 70),
            ProcessorType.WEB: (40, 60),
            ProcessorType.MATHEMATICAL: (30, 50),
            ProcessorType.CODE: (20, 40),
        },
        
        'E_length_based': {
            ProcessorType.MATHEMATICAL: (100, 120),  # Complex expressions
            ProcessorType.CODE: (90, 110),
            ProcessorType.TEMPORAL: (80, 100),       # Multi-word time
            ProcessorType.WEB: (70, 90),
            ProcessorType.MEASUREMENT: (60, 80),     # Number + unit
            ProcessorType.FINANCIAL: (40, 60),       # Often shorter
            ProcessorType.BASIC_NUMERIC: (20, 40),   # Single numbers
            ProcessorType.TEXT: (0, 20),
        },
    }
    
    def __init__(self, config: Optional[Dict[ProcessorType, Tuple[int, int]]] = None):
        """Initialize with a configuration or use default."""
        self.config = config or self.DEFAULT_CONFIG.copy()
        self._validate_config()
    
    def _validate_config(self):
        """Validate that priority ranges don't have gaps or excessive overlap."""
        for proc_type, (min_p, max_p) in self.config.items():
            if min_p >= max_p:
                raise ValueError(f"Invalid range for {proc_type}: {min_p} >= {max_p}")
            if min_p < 0 or max_p > 200:
                raise ValueError(f"Priority out of bounds for {proc_type}: {min_p}-{max_p}")
    
    @classmethod
    def from_name(cls, name: str) -> 'PriorityConfiguration':
        """Create configuration from a predefined name."""
        if name not in cls.CONFIGURATIONS:
            raise ValueError(f"Unknown configuration: {name}. Available: {list(cls.CONFIGURATIONS.keys())}")
        return cls(cls.CONFIGURATIONS[name].copy())
    
    @classmethod
    def from_file(cls, filepath: Path) -> 'PriorityConfiguration':
        """Load configuration from a JSON file (for language-specific configs)."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Convert string keys to ProcessorType enum
        config = {}
        for proc_name, priority_range in data.get('processor_priorities', {}).items():
            try:
                proc_type = ProcessorType(proc_name)
                config[proc_type] = tuple(priority_range)
            except ValueError:
                logger.warning(f"Unknown processor type in config: {proc_name}")
        
        return cls(config)
    
    def get_priority_range(self, processor_type: ProcessorType) -> Tuple[int, int]:
        """Get the priority range for a processor type."""
        return self.config.get(processor_type, (0, 20))
    
    def scale_priority(self, base_priority: int, processor_type: ProcessorType) -> int:
        """
        Scale a 0-100 base priority to the configured range.
        
        Args:
            base_priority: Priority within processor (0-100)
            processor_type: Type of processor
            
        Returns:
            Scaled priority within configured range
        """
        min_p, max_p = self.get_priority_range(processor_type)
        # Ensure base_priority is within 0-100
        base_priority = max(0, min(100, base_priority))
        return min_p + int((base_priority / 100) * (max_p - min_p))
    
    def apply_to_processor(self, processor, processor_type: ProcessorType):
        """
        Apply priority configuration to a processor's rules.
        
        This modifies the processor's detection rules to use scaled priorities.
        """
        if not hasattr(processor, 'detection_rules'):
            logger.warning(f"Processor {processor.__class__.__name__} has no detection_rules")
            return
        
        min_p, max_p = self.get_priority_range(processor_type)
        num_rules = len(processor.detection_rules)
        
        if num_rules == 0:
            return
        
        # Distribute priorities evenly across rules
        for i, rule in enumerate(processor.detection_rules):
            # Calculate position-based priority (highest priority first)
            position_ratio = i / max(1, num_rules - 1)
            scaled_priority = max_p - int(position_ratio * (max_p - min_p))
            rule.priority = scaled_priority
            
        logger.info(f"Applied priorities {min_p}-{max_p} to {processor.__class__.__name__}")
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the configuration."""
        lines = ["Priority Configuration:"]
        # Sort by minimum priority (descending)
        sorted_config = sorted(self.config.items(), key=lambda x: x[1][0], reverse=True)
        for proc_type, (min_p, max_p) in sorted_config:
            lines.append(f"  {proc_type.value:<15} {min_p:3d} - {max_p:3d}")
        return "\n".join(lines)


# Global instance for current configuration
_current_config: Optional[PriorityConfiguration] = None


def get_current_config() -> PriorityConfiguration:
    """Get the current priority configuration."""
    global _current_config
    if _current_config is None:
        _current_config = PriorityConfiguration()
    return _current_config


def set_current_config(config: PriorityConfiguration):
    """Set the current priority configuration."""
    global _current_config
    _current_config = config
    logger.info(f"Priority configuration updated:\n{config.get_summary()}")


def apply_configuration(config_name: str):
    """Apply a named configuration."""
    config = PriorityConfiguration.from_name(config_name)
    set_current_config(config)
    return config