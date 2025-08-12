#!/usr/bin/env python3
"""
Step 2 of the text formatting pipeline: Entity Detection and Deduplication.

This module contains the entity detection orchestration logic that runs multiple
specialized detectors in priority order and handles entity overlap resolution.
This includes:
- Running detectors in priority order (most specific to most general)
- Entity overlap detection and resolution
- Priority-based entity deduplication
- Final entity list preparation

Extracted from the main TextFormatter to create a modular pipeline architecture.
"""

# Standard library imports
import logging
import time
from typing import Dict, List, Any, Optional

# Third-party imports (conditional)
try:
    from intervaltree import IntervalTree, Interval
    INTERVAL_TREE_AVAILABLE = True
except ImportError:
    INTERVAL_TREE_AVAILABLE = False

# Local imports - common data structures
from stt.text_formatting.common import Entity, EntityType

# Local imports - universal priority system
from stt.text_formatting.universal_priority_manager import get_priority_manager

# Theory 12: Entity Interaction Conflict Resolution
from stt.text_formatting.entity_conflict_resolver import resolve_entity_conflicts
from stt.text_formatting.filename_post_processor import post_process_filename_entities

# Theory 17: Spanish Conversational Flow Preservation
from stt.text_formatting.spanish_conversational_flow import SpanishConversationalFlowAnalyzer

# PHASE 19: Entity Validation Framework
from stt.text_formatting.formatter_components.validation import create_entity_validator

# Setup logging for this module
logger = logging.getLogger(__name__)

# PHASE 21: Debug Mode Enhancement - Entity Detection Pipeline Tracing
from stt.text_formatting.debug_utils import (
    get_entity_debugger, debug_entity_list, debug_performance, 
    DebugModule, is_debug_enabled
)

# Legacy entity priorities for backward compatibility
# Now replaced by the Universal Priority Manager system
ENTITY_PRIORITIES = None  # Will be set by get_entity_priorities() function


def get_entity_priorities(language: str = "en") -> Dict[EntityType, int]:
    """
    Get entity priorities for the specified language using the Universal Priority Manager.
    
    This function replaces the hardcoded ENTITY_PRIORITIES dictionary with
    language-aware priority resolution.
    
    Args:
        language: Language code (e.g., 'en', 'es', 'fr')
        
    Returns:
        Dictionary mapping EntityType to priority values
    """
    priority_manager = get_priority_manager(language)
    return priority_manager.get_all_priorities()


@debug_performance("entity_detection", DebugModule.DETECTION)
def detect_all_entities(
    text: str,
    detectors: Dict[str, Any],
    nlp_model: Optional[Any] = None,
    existing_entities: Optional[List[Entity]] = None,
    doc: Optional[Any] = None,
    pipeline_state: Optional[Any] = None,
    language: str = "en"
) -> List[Entity]:
    """
    Run all entity detectors in priority order and return deduplicated final entities.
    
    Theory 9: Universal Cross-Language Entity Priority System
    Uses language-specific priority matrices for smart conflict resolution.
    
    Phase D Optimized: Uses interval trees for O(n log n) entity deduplication and filtering
    vs original O(n²) performance. Maintains identical behavior and logic.
    
    Originally from TextFormatter.format_transcription() (lines 128-165) plus deduplication logic.
    
    Args:
        text: Text to analyze for entities
        detectors: Dictionary containing detector instances:
            - web_detector: WebEntityDetector instance
            - spoken_letter_detector: SpokenLetterDetector instance  
            - code_detector: CodeEntityDetector instance
            - numeric_detector: NumericalEntityDetector instance
            - entity_detector: EntityDetector instance (base SpaCy)
        nlp_model: SpaCy model instance (unused in current implementation)
        existing_entities: Pre-existing entities to include (default: empty list)
        doc: Pre-processed SpaCy document for efficiency
        pipeline_state: Pipeline state object for context
        language: Language code for priority resolution (e.g., 'en', 'es')
        
    Returns:
        List of deduplicated entities sorted by start position
    """
    start_time = time.perf_counter()
    
    # PHASE 21: Debug tracing - Detection start
    debugger = get_entity_debugger()
    debugger.trace_pipeline_state(
        "detection_start", 
        text, 
        existing_entities or [],
        {"language": language, "detectors": list(detectors.keys())}
    )
    
    if existing_entities is None:
        existing_entities = []
    
    # Start with any pre-existing entities
    final_entities: List[Entity] = list(existing_entities)
    
    logger.debug(f"Phase D: Starting entity detection for text of length {len(text)}")
    logger.debug(f"Phase D: Interval tree optimization {'ENABLED' if INTERVAL_TREE_AVAILABLE else 'DISABLED'}")
    
    # PHASE 21: Debug tracing - Log existing entities
    if existing_entities and is_debug_enabled(DebugModule.DETECTION):
        debug_entity_list(
            existing_entities, 
            "detection", 
            "existing_entities",
            DebugModule.DETECTION,
            text=text
        )
    
    # Theory 17: Initialize conversational flow analysis for Spanish
    conversational_analyzer = None
    conversational_entities = []
    if language == "es":
        conversational_analyzer = SpanishConversationalFlowAnalyzer(language)
        if conversational_analyzer.is_conversational_instruction(text):
            logger.info("THEORY_17: Detected conversational Spanish instruction context")
            
            # Detect conversational entities and convert them to standard Entity objects
            conv_entities = conversational_analyzer.identify_conversational_entities(text)
            for conv_entity in conv_entities:
                # Create standard Entity objects from conversational entities
                if conv_entity.conversational_replacement:
                    standard_entity = Entity(
                        text=conv_entity.text,
                        start=conv_entity.start,
                        end=conv_entity.end,
                        type=conv_entity.entity_type
                    )
                    conversational_entities.append(standard_entity)
            
            logger.info(f"THEORY_17: Found {len(conversational_entities)} conversational entities")
            
            # Store conversational context in pipeline state for downstream processing
            if pipeline_state:
                pipeline_state.conversational_context = True
                pipeline_state.conversational_analyzer = conversational_analyzer
    
    # Run detectors from most specific to most general.
    # Each detector is passed the list of entities found so far and should not
    # create new entities that overlap with existing ones.
    
    # Code and Web entities are highly specific and should run first.
    web_entities = detectors["web_detector"].detect(text, final_entities, doc=doc)
    final_entities.extend(web_entities)
    logger.info(f"Web entities detected: {len(web_entities)} - {[f'{e.type}:{e.text}' for e in web_entities]}")
    
    # PHASE 21: Debug tracing - Web entities
    if is_debug_enabled(DebugModule.DETECTION):
        debug_entity_list(
            web_entities, 
            "detection", 
            "web_detector",
            DebugModule.DETECTION,
            text=text,
            detector_type="web_detector",
            total_so_far=len(final_entities)
        )
    
    # Spoken letters are very specific patterns and should run early to avoid conflicts
    letter_entities = detectors["spoken_letter_detector"].detect(text, final_entities, doc=doc)
    final_entities.extend(letter_entities)
    logger.info(
        f"Letter entities detected: {len(letter_entities)} - {[f'{e.type}:{e.text}' for e in letter_entities]}"
    )
    
    # PHASE 21: Debug tracing - Letter entities
    if is_debug_enabled(DebugModule.DETECTION):
        debug_entity_list(
            letter_entities, 
            "detection", 
            "spoken_letter_detector",
            DebugModule.DETECTION,
            text=text,
            detector_type="spoken_letter_detector",
            total_so_far=len(final_entities)
        )
    
    code_entities = detectors["code_detector"].detect(text, final_entities, doc=doc, pipeline_state=pipeline_state)
    final_entities.extend(code_entities)
    logger.info(f"Code entities detected: {len(code_entities)} - {[f'{e.type}:{e.text}' for e in code_entities]}")
    
    # PHASE 21: Debug tracing - Code entities
    if is_debug_enabled(DebugModule.DETECTION):
        debug_entity_list(
            code_entities, 
            "detection", 
            "code_detector",
            DebugModule.DETECTION,
            text=text,
            detector_type="code_detector",
            total_so_far=len(final_entities)
        )
    
    # Numeric entities are next, as they are more specific than base SpaCy entities.
    numeric_entities = detectors["numeric_detector"].detect(text, final_entities, doc=doc)
    final_entities.extend(numeric_entities)
    logger.info(
        f"Numeric entities detected: {len(numeric_entities)} - {[f'{e.type}:{e.text}' for e in numeric_entities]}"
    )
    
    # PHASE 21: Debug tracing - Numeric entities
    if is_debug_enabled(DebugModule.DETECTION):
        debug_entity_list(
            numeric_entities, 
            "detection", 
            "numeric_detector",
            DebugModule.DETECTION,
            text=text,
            detector_type="numeric_detector",
            total_so_far=len(final_entities)
        )
    
    # Finally, run the base SpaCy detector for general entities like DATE, TIME, etc.
    base_spacy_entities = detectors["entity_detector"].detect_entities(text, final_entities, doc=doc)
    final_entities.extend(base_spacy_entities)
    logger.info(
        f"Base SpaCy entities detected: {len(base_spacy_entities)} - {[f'{e.type}:{e.text}' for e in base_spacy_entities]}"
    )
    
    # PHASE 21: Debug tracing - Base SpaCy entities
    if is_debug_enabled(DebugModule.DETECTION):
        debug_entity_list(
            base_spacy_entities, 
            "detection", 
            "entity_detector",
            DebugModule.DETECTION,
            text=text,
            detector_type="entity_detector",
            total_so_far=len(final_entities)
        )
    
    # Theory 17: Add conversational entities to the final list
    final_entities.extend(conversational_entities)
    if conversational_entities:
        logger.info(f"THEORY_17: Added {len(conversational_entities)} conversational entities to final list")
    
    # Get language-specific priorities for this processing run
    entity_priorities = get_entity_priorities(language)
    
    # PHASE 21: Debug tracing - Pre-deduplication state
    if is_debug_enabled(DebugModule.DETECTION):
        debug_entity_list(
            final_entities,
            "detection",
            "pre_deduplication",
            DebugModule.DETECTION,
            text=text,
            total_before_dedup=len(final_entities),
            unique_types=len(set(e.type for e in final_entities))
        )
    
    # Apply deduplication and overlap resolution with language-aware priorities
    deduplicated_entities = _deduplicate_entities(final_entities, entity_priorities)
    
    # PHASE 21: Debug tracing - Post-deduplication
    if is_debug_enabled(DebugModule.DETECTION):
        debug_entity_list(
            deduplicated_entities,
            "detection", 
            "post_deduplication",
            DebugModule.DETECTION,
            text=text,
            entities_removed=len(final_entities) - len(deduplicated_entities),
            deduplication_ratio=f"{len(deduplicated_entities)}/{len(final_entities)}"
        )
    
    # Apply priority-based filtering to remove contained/overlapping lower-priority entities
    priority_filtered_entities = _apply_priority_filtering(deduplicated_entities, entity_priorities)
    
    # PHASE 21: Debug tracing - Post-priority-filtering
    if is_debug_enabled(DebugModule.DETECTION):
        debug_entity_list(
            priority_filtered_entities,
            "detection",
            "post_priority_filtering", 
            DebugModule.DETECTION,
            text=text,
            entities_filtered=len(deduplicated_entities) - len(priority_filtered_entities),
            final_count=len(priority_filtered_entities)
        )
    
    # PHASE 19: Entity Validation Framework - Validate detected entities for consistency
    validator = create_entity_validator(language)
    is_valid, validation_warnings = validator.validate_entity_list_consistency(priority_filtered_entities, text)
    
    if validation_warnings:
        logger.debug(f"PHASE_19_VALIDATION: Entity validation warnings in detection: {len(validation_warnings)} issues found")
        for warning in validation_warnings:
            logger.debug(f"PHASE_19_VALIDATION: {warning}")
    
    # Continue processing regardless of validation warnings (robustness only, no functionality change)
    validated_entities = priority_filtered_entities
    
    # Theory 12: Apply targeted fixes for specific entity detection issues
    # Focus on filename over-detection which causes many test failures
    post_processed_entities = post_process_filename_entities(validated_entities, text)
    
    # Theory 12: Apply advanced entity conflict resolution for remaining edge cases
    # This handles complex interaction conflicts that basic priority filtering misses
    # DISABLED temporarily - existing system works well, focus on detection improvements
    # conflict_resolved_entities = resolve_entity_conflicts(post_processed_entities, text, language)
    conflict_resolved_entities = post_processed_entities
    
    # Performance monitoring
    elapsed = time.perf_counter() - start_time
    total_entities = len(final_entities)
    final_count = len(conflict_resolved_entities)
    
    logger.debug(f"Phase D: Entity detection completed in {elapsed:.4f}s")
    logger.debug(f"Phase D: Processed {total_entities} raw entities -> {final_count} final entities")
    if total_entities > 100:  # Log performance stats for larger entity sets
        logger.info(f"Phase D: Large entity set processed ({total_entities} entities) in {elapsed:.4f}s")
    
    # PHASE 21: Debug tracing - Final detection results
    final_sorted_entities = sorted(conflict_resolved_entities, key=lambda e: e.start)
    if is_debug_enabled(DebugModule.DETECTION):
        debugger.trace_pipeline_state(
            "detection_complete",
            text,
            final_sorted_entities,
            {
                "total_raw_entities": total_entities,
                "final_entities": final_count,
                "processing_time": elapsed,
                "language": language,
                "efficiency_ratio": f"{final_count}/{total_entities}" if total_entities > 0 else "0/0"
            }
        )
        
        # Log performance if enabled
        debugger.trace_performance("detect_all_entities", elapsed, DebugModule.DETECTION)
    
    # Return final sorted list
    return final_sorted_entities


def _deduplicate_entities(entities: List[Entity], entity_priorities: Dict[EntityType, int]) -> List[Entity]:
    """
    Deduplicate entities with identical boundaries and resolve overlapping entities.
    
    Theory 9: Uses language-specific priority matrices for conflict resolution.
    
    Optimized using interval trees for O(n log n) performance vs original O(n²).
    Maintains IDENTICAL behavior and logic to the original implementation.
    
    Args:
        entities: List of entities that may have overlaps or duplicates
        entity_priorities: Language-specific priority dictionary
        
    Returns:
        List of entities with overlaps resolved based on priority and length
    """
    if INTERVAL_TREE_AVAILABLE and len(entities) > 50:  # Use optimization for larger entity sets
        return _deduplicate_entities_optimized(entities, entity_priorities)
    else:
        return _deduplicate_entities_fallback(entities, entity_priorities)


def _deduplicate_entities_optimized(entities: List[Entity], entity_priorities: Dict[EntityType, int]) -> List[Entity]:
    """
    Optimized O(n log n) deduplication using interval trees.
    
    Theory 9: Uses language-specific priority matrices for conflict resolution.
    
    Maintains IDENTICAL behavior to original implementation.
    """
    start_time = time.perf_counter()
    deduplicated_entities: List[Entity] = []
    
    logger.debug(f"Starting optimized deduplication with {len(entities)} entities")
    
    # Build interval tree for efficient overlap queries
    interval_tree = IntervalTree()
    entity_map = {}  # Maps intervals to entities
    
    for entity in entities:
        # Check if this entity overlaps with any already accepted entity
        overlapping_intervals = list(interval_tree.overlap(entity.start, entity.end))
        overlaps_with_existing = False
        
        for interval in overlapping_intervals:
            existing = entity_map[interval]
            
            # Prefer longer entity (more specific) or same type
            entity_length = entity.end - entity.start
            existing_length = existing.end - existing.start
            
            # Get priorities for both entities
            entity_priority = entity_priorities.get(entity.type, 0)
            existing_priority = entity_priorities.get(existing.type, 0)

            # Priority is the primary factor - length is only a tiebreaker for same priority
            if entity_priority > existing_priority:
                # Remove the lower priority entity and add this higher priority one
                deduplicated_entities.remove(existing)
                interval_tree.remove(interval)
                del entity_map[interval]
                logger.debug(
                    f"Replacing lower priority entity {existing.type}('{existing.text}', priority={existing_priority}) with higher priority {entity.type}('{entity.text}', priority={entity_priority})"
                )
                break
            elif entity_priority < existing_priority:
                # Keep the existing higher priority entity
                overlaps_with_existing = True
                logger.debug(
                    f"Skipping lower priority entity: {entity.type}('{entity.text}', priority={entity_priority}) overlaps with higher priority {existing.type}('{existing.text}', priority={existing_priority})"
                )
                break
            else:
                # Same priority - use length as tiebreaker (longer is more specific)
                if entity_length > existing_length:
                    # Remove the shorter existing entity and add this longer one
                    deduplicated_entities.remove(existing)
                    interval_tree.remove(interval)
                    del entity_map[interval]
                    logger.debug(
                        f"Replacing shorter entity {existing.type}('{existing.text}') with longer {entity.type}('{entity.text}') (same priority={entity_priority})"
                    )
                    break
                else:
                    # Keep the existing longer or equal-length entity
                    overlaps_with_existing = True
                    logger.debug(
                        f"Skipping overlapping entity: {entity.type}('{entity.text}') overlaps with {existing.type}('{existing.text}') (same priority={entity_priority})"
                    )
                    break

        if not overlaps_with_existing:
            deduplicated_entities.append(entity)
            new_interval = Interval(entity.start, entity.end)
            interval_tree.add(new_interval)
            entity_map[new_interval] = entity
            logger.debug(f"Added entity: {entity.type}('{entity.text}') at [{entity.start}:{entity.end}]")
    
    elapsed = time.perf_counter() - start_time
    logger.debug(f"Optimized deduplication completed in {elapsed:.4f}s")
    return deduplicated_entities


def _deduplicate_entities_fallback(entities: List[Entity], entity_priorities: Dict[EntityType, int]) -> List[Entity]:
    """
    Original O(n²) deduplication for compatibility/fallback.
    
    Theory 9: Uses language-specific priority matrices for conflict resolution.
    
    Identical to original TextFormatter.format_transcription() (lines 247-306).
    """
    start_time = time.perf_counter()
    deduplicated_entities: List[Entity] = []
    
    logger.debug(f"Starting fallback deduplication with {len(entities)} entities:")
    for i, entity in enumerate(entities):
        logger.debug(f"  {i}: {entity.type}('{entity.text}') at [{entity.start}:{entity.end}]")
    
    def entities_overlap(e1, e2):
        """Check if two entities overlap."""
        return not (e1.end <= e2.start or e2.end <= e1.start)
    
    for entity in entities:
        # Check if this entity overlaps with any already accepted entity
        overlaps_with_existing = False
        for existing in deduplicated_entities:
            if entities_overlap(entity, existing):
                # Prefer longer entity (more specific) or same type
                entity_length = entity.end - entity.start
                existing_length = existing.end - existing.start
                
                # Get priorities for both entities
                entity_priority = entity_priorities.get(entity.type, 0)
                existing_priority = entity_priorities.get(existing.type, 0)

                # Priority is the primary factor - length is only a tiebreaker for same priority
                if entity_priority > existing_priority:
                    # Remove the lower priority entity and add this higher priority one
                    deduplicated_entities.remove(existing)
                    logger.debug(
                        f"Replacing lower priority entity {existing.type}('{existing.text}', priority={existing_priority}) with higher priority {entity.type}('{entity.text}', priority={entity_priority})"
                    )
                    break
                elif entity_priority < existing_priority:
                    # Keep the existing higher priority entity
                    overlaps_with_existing = True
                    logger.debug(
                        f"Skipping lower priority entity: {entity.type}('{entity.text}', priority={entity_priority}) overlaps with higher priority {existing.type}('{existing.text}', priority={existing_priority})"
                    )
                    break
                else:
                    # Same priority - use length as tiebreaker (longer is more specific)
                    if entity_length > existing_length:
                        # Remove the shorter existing entity and add this longer one
                        deduplicated_entities.remove(existing)
                        logger.debug(
                            f"Replacing shorter entity {existing.type}('{existing.text}') with longer {entity.type}('{entity.text}') (same priority={entity_priority})"
                        )
                        break
                    else:
                        # Keep the existing longer or equal-length entity
                        overlaps_with_existing = True
                        logger.debug(
                            f"Skipping overlapping entity: {entity.type}('{entity.text}') overlaps with {existing.type}('{existing.text}') (same priority={entity_priority})"
                        )
                        break

        if not overlaps_with_existing:
            deduplicated_entities.append(entity)
            logger.debug(f"Added entity: {entity.type}('{entity.text}') at [{entity.start}:{entity.end}]")
    
    elapsed = time.perf_counter() - start_time
    logger.debug(f"Fallback deduplication completed in {elapsed:.4f}s")
    return deduplicated_entities


def _apply_priority_filtering(entities: List[Entity], entity_priorities: Dict[EntityType, int]) -> List[Entity]:
    """
    Remove smaller entities that are completely contained within larger, higher-priority entities.
    
    Theory 9: Uses language-specific priority matrices for conflict resolution.
    
    Optimized using interval trees for O(n log n) performance vs original O(n²).
    Maintains IDENTICAL behavior and logic to the original implementation.
    
    Originally from TextFormatter.format_transcription() (lines 308-335).
    
    Args:
        entities: List of deduplicated entities
        entity_priorities: Language-specific priority dictionary
        
    Returns:
        List of entities with contained lower-priority entities removed
    """
    if not entities:
        return []
    
    if INTERVAL_TREE_AVAILABLE and len(entities) > 50:  # Use optimization for larger entity sets
        return _apply_priority_filtering_optimized(entities, entity_priorities)
    else:
        return _apply_priority_filtering_fallback(entities, entity_priorities)


def _apply_priority_filtering_optimized(entities: List[Entity], entity_priorities: Dict[EntityType, int]) -> List[Entity]:
    """
    Optimized O(n log n) priority filtering using interval trees.
    
    Theory 9: Uses language-specific priority matrices for conflict resolution.
    
    Maintains IDENTICAL behavior to original implementation.
    """
    start_time = time.perf_counter()
    
    # Sort entities by priority (highest first) for efficient processing
    sorted_entities = sorted(entities, key=lambda e: (-entity_priorities.get(e.type, 0), e.start))
    
    # Build interval tree with accepted entities
    interval_tree = IntervalTree()
    entity_map = {}  # Maps intervals to entities
    priority_filtered_entities = []
    
    logger.debug(f"Starting optimized priority filtering with {len(entities)} entities")
    
    for entity in sorted_entities:
        is_contained = False
        entity_priority = entity_priorities.get(entity.type, 0)
        
        # Find all overlapping intervals
        overlapping_intervals = list(interval_tree.overlap(entity.start, entity.end))
        
        for interval in overlapping_intervals:
            other_entity = entity_map[interval]
            other_priority = entity_priorities.get(other_entity.type, 0)
            
            if other_priority > entity_priority:
                # Check if entity is completely contained within other_entity OR overlaps with higher priority
                is_contained_within = other_entity.start <= entity.start and entity.end <= other_entity.end
                is_overlapping = not (entity.end <= other_entity.start or other_entity.end <= entity.start)

                if is_contained_within or is_overlapping:
                    action = "contained within" if is_contained_within else "overlapping with"
                    logger.debug(
                        f"Removing lower-priority entity: {entity.type}('{entity.text}') "
                        f"{action} {other_entity.type}('{other_entity.text}')"
                    )
                    is_contained = True
                    break

        if not is_contained:
            priority_filtered_entities.append(entity)
            new_interval = Interval(entity.start, entity.end)
            interval_tree.add(new_interval)
            entity_map[new_interval] = entity

    elapsed = time.perf_counter() - start_time
    logger.debug(f"Optimized priority filtering completed in {elapsed:.4f}s")
    logger.debug(f"Found {len(priority_filtered_entities)} final non-overlapping entities:")
    for i, entity in enumerate(priority_filtered_entities):
        logger.debug(f"  Final {i}: {entity.type}('{entity.text}') at [{entity.start}:{entity.end}]")
    
    return priority_filtered_entities


def _apply_priority_filtering_fallback(entities: List[Entity], entity_priorities: Dict[EntityType, int]) -> List[Entity]:
    """
    Original O(n²) priority filtering for compatibility/fallback.
    
    Theory 9: Uses language-specific priority matrices for conflict resolution.
    
    Identical to original TextFormatter.format_transcription() (lines 308-335).
    """
    start_time = time.perf_counter()
    priority_filtered_entities = []
    
    # Sort entities by start position for better cache locality and potential optimizations
    sorted_entities = sorted(entities, key=lambda e: e.start)
    
    logger.debug(f"Starting fallback priority filtering with {len(entities)} entities")
    
    for entity in sorted_entities:
        is_contained = False
        
        # Check against all other entities for overlaps and containment
        # This preserves the exact original O(n²) logic but with better cache performance
        for other_entity in sorted_entities:
            if entity == other_entity:
                continue

            # Check if entity is completely contained within other_entity OR overlaps with higher priority
            # This is IDENTICAL to the original algorithm logic
            is_contained_within = other_entity.start <= entity.start and entity.end <= other_entity.end
            is_overlapping = not (entity.end <= other_entity.start or other_entity.end <= entity.start)
            has_higher_priority = entity_priorities.get(other_entity.type, 0) > entity_priorities.get(
                entity.type, 0
            )

            if (is_contained_within or is_overlapping) and has_higher_priority:
                action = "contained within" if is_contained_within else "overlapping with"
                logger.debug(
                    f"Removing lower-priority entity: {entity.type}('{entity.text}') "
                    f"{action} {other_entity.type}('{other_entity.text}')"
                )
                is_contained = True
                break

        if not is_contained:
            priority_filtered_entities.append(entity)

    elapsed = time.perf_counter() - start_time
    logger.debug(f"Fallback priority filtering completed in {elapsed:.4f}s")
    logger.debug(f"Found {len(priority_filtered_entities)} final non-overlapping entities:")
    for i, entity in enumerate(priority_filtered_entities):
        logger.debug(f"  Final {i}: {entity.type}('{entity.text}') at [{entity.start}:{entity.end}]")
    
    return priority_filtered_entities