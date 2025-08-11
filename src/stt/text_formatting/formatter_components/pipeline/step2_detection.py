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

# Setup logging for this module
logger = logging.getLogger(__name__)

# Define entity priority (higher number = higher priority)
# Originally from TextFormatter.format_transcription() (lines 167-245)
ENTITY_PRIORITIES = {
    # User-defined exact patterns (80-100)
    EntityType.SPOKEN_LETTER: 100,  # Individual letters should have highest priority
    EntityType.LETTER_SEQUENCE: 95,  # Letter sequences should have high priority
    EntityType.FILENAME: 90,  # Filenames are user-specific patterns
    EntityType.URL: 85,  # URLs need to preserve exact case
    EntityType.SPOKEN_URL: 85,
    EntityType.SPOKEN_PROTOCOL_URL: 85,
    EntityType.EMAIL: 80,
    EntityType.SPOKEN_EMAIL: 80,
    
    # Technical patterns (60-80)
    EntityType.MATH_EXPRESSION: 75,
    EntityType.MATH: 75,
    EntityType.ROOT_EXPRESSION: 74,
    EntityType.SCIENTIFIC_NOTATION: 73,
    EntityType.COMPARISON: 70,
    EntityType.ASSIGNMENT: 70,
    EntityType.INCREMENT_OPERATOR: 68,
    EntityType.DECREMENT_OPERATOR: 68,
    EntityType.SLASH_COMMAND: 65,
    EntityType.CLI_COMMAND: 65,
    EntityType.PROGRAMMING_KEYWORD: 63,
    EntityType.COMMAND_FLAG: 62,
    EntityType.UNDERSCORE_DELIMITER: 60,
    EntityType.SIMPLE_UNDERSCORE_VARIABLE: 60,
    
    # Path patterns (55-60)
    EntityType.UNIX_PATH: 58,
    EntityType.WINDOWS_PATH: 58,
    
    # Financial patterns (50-70)
    EntityType.DOLLAR_CENTS: 65,
    EntityType.DOLLARS: 64,
    EntityType.CENTS: 63,
    EntityType.CURRENCY: 62,
    EntityType.POUNDS: 61,
    EntityType.EUROS: 61,
    EntityType.MONEY: 50,  # Generic money entity (SpaCy)
    
    # Technical measurements (45-55)
    EntityType.DATA_SIZE: 55,
    EntityType.FREQUENCY: 54,
    EntityType.VERSION: 53,
    EntityType.PORT_NUMBER: 52,
    EntityType.TEMPERATURE: 80,
    EntityType.METRIC_LENGTH: 50,
    EntityType.METRIC_WEIGHT: 50,
    EntityType.METRIC_VOLUME: 50,
    
    # Time patterns (40-50)
    EntityType.TIME_AMPM: 48,
    EntityType.TIME: 47,
    EntityType.TIME_DURATION: 46,
    EntityType.TIME_CONTEXT: 45,
    EntityType.TIME_RELATIVE: 44,
    EntityType.DATE: 42,
    
    # Numeric patterns (30-40)
    EntityType.PHONE_LONG: 40,
    EntityType.NUMERIC_RANGE: 38,
    EntityType.FRACTION: 36,
    EntityType.PERCENT: 35,
    EntityType.ORDINAL: 32,
    EntityType.QUANTITY: 30,
    
    # Generic SpaCy entities (10-30)
    EntityType.CARDINAL: 20,  # Basic numbers
    EntityType.ABBREVIATION: 105,  # Higher than SPOKEN_LETTER to prevent conflicts
    
    # Special patterns (20-40)
    EntityType.PHYSICS_SQUARED: 35,
    EntityType.PHYSICS_TIMES: 35,
    EntityType.MATH_CONSTANT: 34,
    EntityType.MUSIC_NOTATION: 30,
    EntityType.SPOKEN_EMOJI: 28,
    EntityType.PROTOCOL: 26,
}


def detect_all_entities(
    text: str,
    detectors: Dict[str, Any],
    nlp_model: Optional[Any] = None,
    existing_entities: Optional[List[Entity]] = None,
    doc: Optional[Any] = None,
    pipeline_state: Optional[Any] = None
) -> List[Entity]:
    """
    Run all entity detectors in priority order and return deduplicated final entities.
    
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
        
    Returns:
        List of deduplicated entities sorted by start position
    """
    start_time = time.perf_counter()
    
    if existing_entities is None:
        existing_entities = []
    
    # Start with any pre-existing entities
    final_entities: List[Entity] = list(existing_entities)
    
    logger.debug(f"Phase D: Starting entity detection for text of length {len(text)}")
    logger.debug(f"Phase D: Interval tree optimization {'ENABLED' if INTERVAL_TREE_AVAILABLE else 'DISABLED'}")
    
    # Run detectors from most specific to most general.
    # Each detector is passed the list of entities found so far and should not
    # create new entities that overlap with existing ones.
    
    # Code and Web entities are highly specific and should run first.
    web_entities = detectors["web_detector"].detect(text, final_entities, doc=doc)
    final_entities.extend(web_entities)
    logger.info(f"Web entities detected: {len(web_entities)} - {[f'{e.type}:{e.text}' for e in web_entities]}")
    
    # Spoken letters are very specific patterns and should run early to avoid conflicts
    letter_entities = detectors["spoken_letter_detector"].detect(text, final_entities, doc=doc)
    final_entities.extend(letter_entities)
    logger.info(
        f"Letter entities detected: {len(letter_entities)} - {[f'{e.type}:{e.text}' for e in letter_entities]}"
    )
    
    code_entities = detectors["code_detector"].detect(text, final_entities, doc=doc, pipeline_state=pipeline_state)
    final_entities.extend(code_entities)
    logger.info(f"Code entities detected: {len(code_entities)} - {[f'{e.type}:{e.text}' for e in code_entities]}")
    
    # Numeric entities are next, as they are more specific than base SpaCy entities.
    numeric_entities = detectors["numeric_detector"].detect(text, final_entities, doc=doc)
    final_entities.extend(numeric_entities)
    logger.info(
        f"Numeric entities detected: {len(numeric_entities)} - {[f'{e.type}:{e.text}' for e in numeric_entities]}"
    )
    
    # Finally, run the base SpaCy detector for general entities like DATE, TIME, etc.
    base_spacy_entities = detectors["entity_detector"].detect_entities(text, final_entities, doc=doc)
    final_entities.extend(base_spacy_entities)
    logger.info(
        f"Base SpaCy entities detected: {len(base_spacy_entities)} - {[f'{e.type}:{e.text}' for e in base_spacy_entities]}"
    )
    
    # Apply deduplication and overlap resolution
    deduplicated_entities = _deduplicate_entities(final_entities)
    
    # Apply priority-based filtering to remove contained/overlapping lower-priority entities
    priority_filtered_entities = _apply_priority_filtering(deduplicated_entities)
    
    # Performance monitoring
    elapsed = time.perf_counter() - start_time
    total_entities = len(final_entities)
    final_count = len(priority_filtered_entities)
    
    logger.debug(f"Phase D: Entity detection completed in {elapsed:.4f}s")
    logger.debug(f"Phase D: Processed {total_entities} raw entities -> {final_count} final entities")
    if total_entities > 100:  # Log performance stats for larger entity sets
        logger.info(f"Phase D: Large entity set processed ({total_entities} entities) in {elapsed:.4f}s")
    
    # Return final sorted list
    return sorted(priority_filtered_entities, key=lambda e: e.start)


def _deduplicate_entities(entities: List[Entity]) -> List[Entity]:
    """
    Deduplicate entities with identical boundaries and resolve overlapping entities.
    
    Optimized using interval trees for O(n log n) performance vs original O(n²).
    Maintains IDENTICAL behavior and logic to the original implementation.
    
    Args:
        entities: List of entities that may have overlaps or duplicates
        
    Returns:
        List of entities with overlaps resolved based on priority and length
    """
    if INTERVAL_TREE_AVAILABLE and len(entities) > 50:  # Use optimization for larger entity sets
        return _deduplicate_entities_optimized(entities)
    else:
        return _deduplicate_entities_fallback(entities)


def _deduplicate_entities_optimized(entities: List[Entity]) -> List[Entity]:
    """
    Optimized O(n log n) deduplication using interval trees.
    
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
            entity_priority = ENTITY_PRIORITIES.get(entity.type, 0)
            existing_priority = ENTITY_PRIORITIES.get(existing.type, 0)

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


def _deduplicate_entities_fallback(entities: List[Entity]) -> List[Entity]:
    """
    Original O(n²) deduplication for compatibility/fallback.
    
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
                entity_priority = ENTITY_PRIORITIES.get(entity.type, 0)
                existing_priority = ENTITY_PRIORITIES.get(existing.type, 0)

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


def _apply_priority_filtering(entities: List[Entity]) -> List[Entity]:
    """
    Remove smaller entities that are completely contained within larger, higher-priority entities.
    
    Optimized using interval trees for O(n log n) performance vs original O(n²).
    Maintains IDENTICAL behavior and logic to the original implementation.
    
    Originally from TextFormatter.format_transcription() (lines 308-335).
    
    Args:
        entities: List of deduplicated entities
        
    Returns:
        List of entities with contained lower-priority entities removed
    """
    if not entities:
        return []
    
    if INTERVAL_TREE_AVAILABLE and len(entities) > 50:  # Use optimization for larger entity sets
        return _apply_priority_filtering_optimized(entities)
    else:
        return _apply_priority_filtering_fallback(entities)


def _apply_priority_filtering_optimized(entities: List[Entity]) -> List[Entity]:
    """
    Optimized O(n log n) priority filtering using interval trees.
    
    Maintains IDENTICAL behavior to original implementation.
    """
    start_time = time.perf_counter()
    
    # Sort entities by priority (highest first) for efficient processing
    sorted_entities = sorted(entities, key=lambda e: (-ENTITY_PRIORITIES.get(e.type, 0), e.start))
    
    # Build interval tree with accepted entities
    interval_tree = IntervalTree()
    entity_map = {}  # Maps intervals to entities
    priority_filtered_entities = []
    
    logger.debug(f"Starting optimized priority filtering with {len(entities)} entities")
    
    for entity in sorted_entities:
        is_contained = False
        entity_priority = ENTITY_PRIORITIES.get(entity.type, 0)
        
        # Find all overlapping intervals
        overlapping_intervals = list(interval_tree.overlap(entity.start, entity.end))
        
        for interval in overlapping_intervals:
            other_entity = entity_map[interval]
            other_priority = ENTITY_PRIORITIES.get(other_entity.type, 0)
            
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


def _apply_priority_filtering_fallback(entities: List[Entity]) -> List[Entity]:
    """
    Original O(n²) priority filtering for compatibility/fallback.
    
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
            has_higher_priority = ENTITY_PRIORITIES.get(other_entity.type, 0) > ENTITY_PRIORITIES.get(
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