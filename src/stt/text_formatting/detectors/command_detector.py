#!/usr/bin/env python3
"""Command-related entity detection for code transcriptions."""
from __future__ import annotations

import re

from stt.core.config import setup_logging
from stt.text_formatting import regex_patterns
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.constants import get_resources
from stt.text_formatting.pattern_cache import cached_pattern
from stt.text_formatting.utils import is_inside_entity

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


# Cached pattern helper functions
@cached_pattern
def build_preformatted_flag_pattern() -> re.Pattern[str]:
    """Build preformatted flag pattern."""
    return re.compile(r"--[A-Z][A-Z0-9_-]*", re.IGNORECASE)


class CommandDetector:
    """Detects command-related entities like CLI commands, slash commands, and flags."""

    def __init__(self, language: str = "en"):
        """
        Initialize CommandDetector.

        Args:
            language: Language code for resource loading (default: 'en')
        """
        self.language = language
        self.resources = get_resources(language)

        # Build patterns dynamically for the specified language
        self.slash_command_pattern = regex_patterns.get_slash_command_pattern(language)
        self.long_flag_pattern = regex_patterns.get_long_flag_pattern(language)
        self.short_flag_pattern = regex_patterns.get_short_flag_pattern(language)

    def detect_cli_commands(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detects standalone CLI commands and keywords."""
        if all_entities is None:
            all_entities = entities

        resources = get_resources(self.language)
        multi_word_commands = resources.get("context_words", {}).get("multi_word_commands", [])

        # Only use specific CLI tools and multi-word commands, not all technical terms
        cli_tools = {
            "git",
            "npm",
            "pip",
            "docker",
            "kubectl",
            "cargo",
            "yarn",
            "brew",
            "apt",
            "make",
            "cmake",
            "node",
            "python",
            "java",
            "mvn",
            "gradle",
            "composer",
            "gem",
            "conda",
            "helm",
            "terraform",
            "ansible",
            "vagrant",
        }

        # Combine CLI tools with multi-word technical terms and sort by length
        all_commands = sorted(list(multi_word_commands) + list(cli_tools), key=len, reverse=True)

        for command in all_commands:
            # Use regex to find whole-word matches
            pattern = rf"\b{re.escape(command)}\b"
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if not is_inside_entity(match.start(), match.end(), all_entities):
                    # Check if this command is in a filename context (preceded by "dot")
                    # This prevents CLI commands like "java" from being detected when they're
                    # part of filename patterns like "user service dot java"
                    is_filename_context = self._is_in_filename_context(text, match)
                    
                    if not is_filename_context:
                        new_entity = Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(0),
                            type=EntityType.CLI_COMMAND,
                            metadata={"command": match.group(0)},
                        )
                        entities.append(new_entity)
                        # Update all_entities to include newly found entity for subsequent overlap checks
                        all_entities.append(new_entity)

    def detect_command_flags(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detects spoken command-line flags like 'dash dash verbose' or 'dash f'."""
        # Pattern for long flags: --flag
        for match in self.long_flag_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                logger.debug(f"Found long flag: '{match.group(0)}' -> '--{match.group(1)}'")
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.COMMAND_FLAG,
                        metadata={"type": "long", "name": match.group(1)},
                    )
                )

        # Pattern for short flags: -f or -flag
        # But make sure we don't match long flags we already detected
        for match in self.short_flag_pattern.finditer(text):
            # Include both original entities and newly detected entities for overlap checking
            check_entities = (all_entities if all_entities else []) + entities
            # Ensure we don't overlap with a long flag we just detected
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Also make sure this isn't part of "dash dash" by checking preceding context
                # Get preceding characters to check for another "dash"
                preceding_text = text[max(0, match.start() - 10) : match.start()].strip()
                if not preceding_text.endswith("dash"):
                    logger.debug(f"Found short flag: '{match.group(0)}' -> '-{match.group(1)}'")
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(0),
                            type=EntityType.COMMAND_FLAG,
                            metadata={"type": "short", "name": match.group(1)},
                        )
                    )

    def detect_preformatted_flags(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detects already-formatted command flags (like --MESSAGE) and normalizes them to lowercase."""
        if all_entities is None:
            all_entities = entities

        # Pattern to match already-formatted flags with uppercase letters
        preformatted_flag_pattern = build_preformatted_flag_pattern()

        for match in preformatted_flag_pattern.finditer(text):
            # Only detect if it has uppercase letters and isn't already detected
            flag_text = match.group(0)
            if any(c.isupper() for c in flag_text) and not is_inside_entity(match.start(), match.end(), all_entities):
                # Extract flag name (everything after --)
                flag_name = flag_text[2:]  # Remove --
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=flag_text,
                        type=EntityType.COMMAND_FLAG,
                        metadata={"type": "preformatted", "name": flag_name.lower()},
                    )
                )
                # Update all_entities to include newly found entity for subsequent overlap checks
                all_entities.append(entities[-1])

    def detect_slash_commands(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detects spoken slash commands like 'slash commit' -> '/commit'."""
        slash_command_pattern = self.slash_command_pattern
        matches = list(slash_command_pattern.finditer(text))

        for i, match in enumerate(matches):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Check if preceded by a number word (likely math division)
                # or if preceded by a URL/domain (likely URL path)
                if match.start() > 0:
                    preceding_text = text[: match.start()].rstrip()
                    # Get the last word before "slash"
                    if preceding_text:
                        words = preceding_text.split()
                        if words:
                            last_word = words[-1].lower()
                            # Check if it's a number word
                            from stt.text_formatting.common import NumberParser

                            parser = NumberParser(language=self.language)
                            if last_word in parser.all_number_words or last_word.isdigit():
                                # Skip this - it's likely division, not a slash command
                                continue
                            
                            # Check if it looks like a URL/domain (contains dots)
                            # This handles cases like "github.com slash project" where "slash project"
                            # should be treated as a URL path, not a slash command
                            if "." in last_word:
                                # Check if it ends with a common TLD or has URL-like structure
                                common_tlds = {
                                    "com", "org", "net", "edu", "gov", "io", "co", "uk", "ca", "au",
                                    "de", "fr", "jp", "cn", "in", "br", "mx", "es", "it", "nl", "local"
                                }
                                if any(last_word.endswith("." + tld) for tld in common_tlds):
                                    # Skip this - it's likely a URL path, not a slash command
                                    continue

                command = match.group(1)

                # Determine if this command has parameters
                # Parameters are text between this command and the next slash command (or end)
                start_pos = match.end()
                if i + 1 < len(matches):
                    # Next slash command exists
                    end_pos = matches[i + 1].start()
                else:
                    # This is the last slash command, check for sentence end
                    end_pos = len(text)
                    # Look for sentence punctuation
                    for punct_pos in range(start_pos, len(text)):
                        if text[punct_pos] in ".!?":
                            end_pos = punct_pos
                            break

                # Extract parameters if any
                parameters = ""
                entity_end = match.end()
                if start_pos < end_pos:
                    potential_params = text[start_pos:end_pos].strip()
                    # Only consider it parameters if it doesn't start with "slash" (another command)
                    if potential_params and not potential_params.lower().startswith("slash"):
                        parameters = potential_params
                        # Extend the entity to include parameters
                        entity_end = end_pos
                        # Remove trailing punctuation from entity boundary
                        while entity_end > start_pos and text[entity_end - 1] in ".!?":
                            entity_end -= 1

                logger.debug(
                    f"Found slash command: '{text[match.start():entity_end]}' -> '/{command}' with params: '{parameters}'"
                )
                entities.append(
                    Entity(
                        start=match.start(),
                        end=entity_end,
                        text=text[match.start() : entity_end],
                        type=EntityType.SLASH_COMMAND,
                        metadata={"command": command, "parameters": parameters},
                    )
                )

    def _is_in_filename_context(self, text: str, match: re.Match) -> bool:
        """
        Check if a command match is in a filename context.
        
        A command is considered to be in filename context if it's preceded by "dot"
        as part of a filename pattern like "script dot py" or "config dot java".
        
        Args:
            text: The full text being analyzed
            match: The regex match object for the potential command
            
        Returns:
            True if the command appears to be part of a filename pattern
        """
        # Look backwards from the match to see if it's preceded by "dot"
        context_start = max(0, match.start() - 20)  # Look back up to 20 characters
        context = text[context_start:match.start()].lower().strip()
        
        # Check if the context ends with "dot" (indicating filename pattern)
        if context.endswith(" dot"):
            logger.debug(f"Command '{match.group()}' appears to be in filename context (preceded by 'dot')")
            return True
            
        return False