#!/usr/bin/env python3
"""
Debug utility infrastructure for entity processing pipeline.

This module provides comprehensive debug tracing capabilities that can be controlled
via environment variables and have zero performance impact when disabled.

Environment Variables:
    STT_DEBUG_ENTITIES: Enable entity debug mode (set to "1", "true", or "on")
    STT_DEBUG_LEVEL: Control debug verbosity (info, debug, trace)
    STT_DEBUG_MODULES: Comma-separated list of modules to debug (detection,conversion,pipeline,all)
"""

import os
import logging
import time
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from stt.text_formatting.common import Entity, EntityType


class DebugLevel(Enum):
    """Debug verbosity levels"""
    INFO = "info"        # Basic operations and results  
    DEBUG = "debug"      # Detailed operations and intermediate states
    TRACE = "trace"      # Maximum verbosity with complete state dumps


class DebugModule(Enum):
    """Debug modules that can be individually controlled"""
    DETECTION = "detection"    # Entity detection pipeline
    CONVERSION = "conversion"  # Entity conversion processing
    PIPELINE = "pipeline"      # Pipeline state management
    ALL = "all"               # All modules


@dataclass
class DebugContext:
    """Context information for debug tracing"""
    operation: str
    module: DebugModule
    start_time: float = field(default_factory=time.perf_counter)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def elapsed(self) -> float:
        """Get elapsed time since context creation"""
        return time.perf_counter() - self.start_time


@dataclass
class EntityDebugInfo:
    """Comprehensive debug information for an entity"""
    entity: Entity
    stage: str
    operation: str
    before_text: Optional[str] = None
    after_text: Optional[str] = None
    position_before: Optional[tuple] = None
    position_after: Optional[tuple] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.perf_counter)
    
    def position_changed(self) -> bool:
        """Check if entity position changed"""
        return (self.position_before and self.position_after and 
                self.position_before != self.position_after)
    
    def text_changed(self) -> bool:
        """Check if entity text changed"""
        return (self.before_text and self.after_text and 
                self.before_text != self.after_text)


class EntityPipelineDebugger:
    """
    Comprehensive debug tracing system for entity processing pipeline.
    
    Features:
    - Zero performance impact when disabled
    - Environment variable controlled activation
    - Module-specific debug filtering  
    - Multi-level verbosity control
    - Entity state tracking across pipeline stages
    - Performance monitoring for bottleneck identification
    """
    
    def __init__(self):
        self._enabled = self._check_debug_enabled()
        self._debug_level = self._get_debug_level()
        self._debug_modules = self._get_debug_modules()
        self._logger = self._setup_logger()
        self._entity_traces: Dict[str, List[EntityDebugInfo]] = {}
        self._performance_stats: Dict[str, List[float]] = {}
        
    def _check_debug_enabled(self) -> bool:
        """Check if entity debugging is enabled via environment variables"""
        debug_var = os.environ.get("STT_DEBUG_ENTITIES", "").lower()
        return debug_var in ("1", "true", "on", "yes")
    
    def _get_debug_level(self) -> DebugLevel:
        """Get debug verbosity level from environment"""
        level_str = os.environ.get("STT_DEBUG_LEVEL", "info").lower()
        try:
            return DebugLevel(level_str)
        except ValueError:
            return DebugLevel.INFO
    
    def _get_debug_modules(self) -> set[DebugModule]:
        """Get enabled debug modules from environment"""
        modules_str = os.environ.get("STT_DEBUG_MODULES", "all").lower()
        module_names = [name.strip() for name in modules_str.split(",")]
        
        modules = set()
        for name in module_names:
            try:
                module = DebugModule(name)
                modules.add(module)
                if module == DebugModule.ALL:
                    return {DebugModule.DETECTION, DebugModule.CONVERSION, DebugModule.PIPELINE}
            except ValueError:
                continue
                
        return modules if modules else {DebugModule.ALL}
    
    def _setup_logger(self) -> logging.Logger:
        """Setup dedicated debug logger"""
        logger = logging.getLogger("stt.text_formatting.debug")
        
        if not self._enabled:
            logger.disabled = True
            return logger
            
        # Only configure if not already configured
        if not logger.handlers:
            logger.setLevel(logging.DEBUG)
            
            # Console handler for debug output
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "🐛 [%(asctime)s] %(levelname)s: %(message)s",
                datefmt="%H:%M:%S.%f"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.propagate = False
            
        return logger
    
    def is_enabled(self, module: DebugModule = DebugModule.ALL) -> bool:
        """Check if debugging is enabled for a specific module"""
        if not self._enabled:
            return False
        return module in self._debug_modules or DebugModule.ALL in self._debug_modules
    
    def create_context(self, operation: str, module: DebugModule, **metadata) -> DebugContext:
        """Create a debug context for tracking an operation"""
        return DebugContext(
            operation=operation,
            module=module,
            metadata=metadata
        )
    
    def trace_entity_operation(
        self,
        entity: Entity,
        stage: str,
        operation: str,
        module: DebugModule,
        before_text: Optional[str] = None,
        after_text: Optional[str] = None,
        **metadata
    ) -> Optional[EntityDebugInfo]:
        """
        Trace an entity operation with comprehensive debug information.
        
        Args:
            entity: The entity being processed
            stage: Pipeline stage (detection, conversion, etc.)
            operation: Specific operation being performed
            module: Debug module category
            before_text: Entity text before operation
            after_text: Entity text after operation
            **metadata: Additional debug metadata
            
        Returns:
            EntityDebugInfo if debugging enabled, None otherwise
        """
        if not self.is_enabled(module):
            return None
            
        # Generate entity key for tracking
        entity_key = f"{entity.type.value}_{entity.start}_{entity.end}_{hash(entity.text) % 10000}"
        
        debug_info = EntityDebugInfo(
            entity=entity,
            stage=stage,
            operation=operation,
            before_text=before_text or entity.text,
            after_text=after_text,
            position_before=(entity.start, entity.end),
            metadata=metadata
        )
        
        # Store trace information
        if entity_key not in self._entity_traces:
            self._entity_traces[entity_key] = []
        self._entity_traces[entity_key].append(debug_info)
        
        # Log based on verbosity level
        self._log_entity_operation(debug_info, module)
        
        return debug_info
    
    def trace_entity_list(
        self,
        entities: List[Entity],
        stage: str,
        operation: str,
        module: DebugModule,
        text: Optional[str] = None,
        **metadata
    ):
        """Trace operations on a list of entities"""
        if not self.is_enabled(module):
            return
            
        self._logger.info(f"🔍 {stage.upper()}: {operation}")
        self._logger.info(f"   📊 Processing {len(entities)} entities")
        
        if text and self._debug_level in (DebugLevel.DEBUG, DebugLevel.TRACE):
            self._logger.debug(f"   📝 Text: {repr(text[:100])}{'...' if len(text) > 100 else ''}")
        
        if self._debug_level == DebugLevel.TRACE:
            for i, entity in enumerate(entities):
                self._logger.debug(
                    f"   [{i:2d}] {entity.type.value:20s} [{entity.start:3d}:{entity.end:3d}] '{entity.text}'"
                )
        
        if metadata:
            for key, value in metadata.items():
                self._logger.debug(f"   🏷️  {key}: {value}")
    
    def trace_entity_conversion(
        self,
        entity: Entity,
        original_text: str,
        converted_text: str,
        converter_name: str,
        success: bool = True,
        error: Optional[str] = None
    ):
        """Trace entity conversion with before/after details"""
        if not self.is_enabled(DebugModule.CONVERSION):
            return
            
        status = "✅" if success else "❌"
        self._logger.info(
            f"{status} CONVERSION: {entity.type.value} '{original_text}' -> '{converted_text}'"
        )
        
        if self._debug_level in (DebugLevel.DEBUG, DebugLevel.TRACE):
            self._logger.debug(f"   🔧 Converter: {converter_name}")
            self._logger.debug(f"   📍 Position: [{entity.start}:{entity.end}]")
            if error:
                self._logger.debug(f"   ⚠️  Error: {error}")
    
    def trace_entity_conflicts(
        self,
        conflicts: List[tuple],
        resolution_strategy: str,
        entities_before: int,
        entities_after: int
    ):
        """Trace entity conflict resolution"""
        if not self.is_enabled(DebugModule.DETECTION):
            return
            
        if conflicts:
            self._logger.info(f"⚔️  CONFLICTS: {len(conflicts)} conflicts detected")
            self._logger.info(f"   🔧 Strategy: {resolution_strategy}")
            self._logger.info(f"   📊 Entities: {entities_before} -> {entities_after}")
            
            if self._debug_level == DebugLevel.TRACE:
                for i, conflict in enumerate(conflicts):
                    self._logger.debug(f"   [{i}] {conflict}")
    
    def trace_performance(self, operation: str, duration: float, module: DebugModule):
        """Trace performance metrics for pipeline operations"""
        if not self.is_enabled(module):
            return
            
        # Store performance data
        if operation not in self._performance_stats:
            self._performance_stats[operation] = []
        self._performance_stats[operation].append(duration)
        
        # Log performance info
        if duration > 0.1:  # Only log slow operations
            self._logger.warning(f"⏱️  SLOW: {operation} took {duration:.4f}s")
        elif self._debug_level == DebugLevel.TRACE:
            self._logger.debug(f"⏱️  {operation}: {duration:.4f}s")
    
    def trace_pipeline_state(
        self,
        stage: str,
        text: str,
        entities: List[Entity],
        state_info: Optional[Dict[str, Any]] = None
    ):
        """Trace pipeline state at key checkpoints"""
        if not self.is_enabled(DebugModule.PIPELINE):
            return
            
        self._logger.info(f"🔄 PIPELINE: {stage}")
        self._logger.info(f"   📝 Text length: {len(text)}")
        self._logger.info(f"   📊 Entities: {len(entities)}")
        
        if self._debug_level in (DebugLevel.DEBUG, DebugLevel.TRACE):
            # Show text preview
            preview = text[:100] + "..." if len(text) > 100 else text
            self._logger.debug(f"   📖 Text: {repr(preview)}")
            
            # Show entity summary
            entity_types = {}
            for entity in entities:
                entity_types[entity.type] = entity_types.get(entity.type, 0) + 1
            
            for entity_type, count in entity_types.items():
                self._logger.debug(f"   📊 {entity_type.value}: {count}")
        
        if state_info and self._debug_level == DebugLevel.TRACE:
            for key, value in state_info.items():
                self._logger.debug(f"   🏷️  {key}: {value}")
    
    def _log_entity_operation(self, debug_info: EntityDebugInfo, module: DebugModule):
        """Log entity operation based on current debug level"""
        entity = debug_info.entity
        
        if self._debug_level == DebugLevel.INFO:
            self._logger.info(
                f"🎯 {debug_info.stage.upper()}: {entity.type.value} '{entity.text}'"
            )
        
        elif self._debug_level == DebugLevel.DEBUG:
            self._logger.debug(
                f"🎯 {debug_info.stage.upper()}: {debug_info.operation}"
            )
            self._logger.debug(
                f"   📍 {entity.type.value} [{entity.start}:{entity.end}] '{entity.text}'"
            )
            
            if debug_info.text_changed():
                self._logger.debug(
                    f"   📝 '{debug_info.before_text}' -> '{debug_info.after_text}'"
                )
        
        elif self._debug_level == DebugLevel.TRACE:
            self._logger.debug(f"🎯 {debug_info.stage.upper()}: {debug_info.operation}")
            self._logger.debug(f"   📍 Type: {entity.type.value}")
            self._logger.debug(f"   📍 Position: [{entity.start}:{entity.end}]")
            self._logger.debug(f"   📝 Text: {repr(entity.text)}")
            
            if debug_info.before_text and debug_info.after_text:
                self._logger.debug(f"   📝 Before: {repr(debug_info.before_text)}")
                self._logger.debug(f"   📝 After: {repr(debug_info.after_text)}")
            
            if debug_info.metadata:
                for key, value in debug_info.metadata.items():
                    self._logger.debug(f"   🏷️  {key}: {value}")
    
    def get_entity_trace(self, entity: Entity) -> List[EntityDebugInfo]:
        """Get complete trace history for an entity"""
        entity_key = f"{entity.type.value}_{entity.start}_{entity.end}_{hash(entity.text) % 10000}"
        return self._entity_traces.get(entity_key, [])
    
    def get_performance_summary(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics summary"""
        summary = {}
        for operation, durations in self._performance_stats.items():
            summary[operation] = {
                "count": len(durations),
                "total": sum(durations),
                "average": sum(durations) / len(durations),
                "min": min(durations),
                "max": max(durations)
            }
        return summary
    
    def dump_debug_summary(self):
        """Dump comprehensive debug summary"""
        if not self._enabled:
            return
            
        self._logger.info("=" * 60)
        self._logger.info("🐛 ENTITY PIPELINE DEBUG SUMMARY")
        self._logger.info("=" * 60)
        
        # Entity trace summary
        total_traces = sum(len(traces) for traces in self._entity_traces.values())
        self._logger.info(f"📊 Total entity traces: {total_traces}")
        self._logger.info(f"📊 Unique entities tracked: {len(self._entity_traces)}")
        
        # Performance summary
        perf_summary = self.get_performance_summary()
        if perf_summary:
            self._logger.info("⏱️  Performance Summary:")
            for operation, stats in perf_summary.items():
                self._logger.info(
                    f"   {operation}: {stats['count']} calls, "
                    f"avg {stats['average']:.4f}s, "
                    f"total {stats['total']:.4f}s"
                )


# Global debug instance
_debug_instance: Optional[EntityPipelineDebugger] = None


def get_entity_debugger() -> EntityPipelineDebugger:
    """Get the global entity pipeline debugger instance"""
    global _debug_instance
    if _debug_instance is None:
        _debug_instance = EntityPipelineDebugger()
    return _debug_instance


def debug_entity_operation(
    entity: Entity,
    stage: str,
    operation: str,
    module: DebugModule = DebugModule.ALL,
    **kwargs
) -> Optional[EntityDebugInfo]:
    """Convenience function for tracing entity operations"""
    debugger = get_entity_debugger()
    return debugger.trace_entity_operation(entity, stage, operation, module, **kwargs)


def debug_entity_list(
    entities: List[Entity],
    stage: str,
    operation: str,
    module: DebugModule = DebugModule.ALL,
    **kwargs
):
    """Convenience function for tracing entity list operations"""
    debugger = get_entity_debugger()
    return debugger.trace_entity_list(entities, stage, operation, module, **kwargs)


def debug_performance(operation: str, module: DebugModule = DebugModule.ALL) -> Callable:
    """Decorator for tracing function performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            debugger = get_entity_debugger()
            if not debugger.is_enabled(module):
                return func(*args, **kwargs)
                
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.perf_counter() - start_time
                debugger.trace_performance(f"{func.__name__}:{operation}", duration, module)
        return wrapper
    return decorator


def is_debug_enabled(module: DebugModule = DebugModule.ALL) -> bool:
    """Check if debugging is enabled for a module"""
    debugger = get_entity_debugger()
    return debugger.is_enabled(module)