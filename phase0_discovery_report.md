# Phase 0: Discovery and Baseline Report

## Project Assessment Summary

### Current Branch
- **Branch:** autonomous-refactor
- **Status:** Clean (no uncommitted changes)

### Test Suite Baseline
- **Total Tests:** 385 (text formatting) + 37 (integration) = 422
- **Passing:** 300 (71.1%)
- **Failing:** 95 text formatting + 10 integration errors + misc = 121
- **Test Execution Command:** `./test.py`
- **Test Suite Locations:**
  - Unit tests: `/workspace/tests/unit/`
  - Integration tests: `/workspace/tests/integration/`
  - Text formatting tests: `/workspace/tests/unit/text_formatting/`

### Main Issues Identified
1. **Missing Context Words in Entity Detection** (65 tests)
   - Entity detectors too aggressive, removing surrounding context
   - Example: "edit the config file settings dot json" → "Edit the settings.json" (missing "config file")

2. **Incorrect Capitalization** (12 tests)
   - Conflicts between sentence-start and entity preservation rules
   - Example: "version one point two" → "version 1.2" (missing capital V)

3. **Missing Punctuation** (8 tests)
   - Punctuation model not applied consistently after entity formatting
   - Example: "flatten the curve" → "Flatten the curve" (missing period)

4. **Failed Operator Conversions** (7 tests)
   - Pattern matching for operators overridden by other detectors
   - Example: "x equals equals y" → "x = equals_y" (should be "x == y")

5. **Abbreviation Handling Issues** (Multiple tests)
   - Latin abbreviations getting incorrect formatting
   - Example: "versus v s other options" → "Versus VS. other options" (should be "vs.")

### Technical Debt Identified (Files >500 lines)
1. **cli.py** - 1884 lines (CRITICAL)
2. **app_hooks.py** - 1418 lines (CRITICAL)
3. **transcription/client.py** - 897 lines
4. **detectors/code_detector.py** - 861 lines
5. **modes/conversation.py** - 848 lines
6. **core/config.py** - 826 lines
7. **pattern_modules/text_patterns.py** - 650 lines
8. **transcription/server.py** - 648 lines
9. **formatter_components/entity_detector.py** - 614 lines
10. **capitalizer.py** - 528 lines

### Project Structure
- **Entry Point:** `stt.py`
- **Core Package:** `src/stt/`
- **Text Formatting Engine:** `src/stt/text_formatting/`
- **Configuration:** `config.json`
- **Test Runner:** `test.py` (enhanced wrapper around pytest)
- **Development Setup:** `./setup.sh install --dev`

### Key Technical Stack
- **Speech Recognition:** faster-whisper, ctranslate2
- **Text Processing:** spacy, deepmultilingualpunctuation
- **Testing:** pytest with custom plugins
- **Audio:** opuslib, pynput
- **Async:** websockets, aiohttp

### Performance Baseline
- Test suite execution time: ~21.83s (sequential mode)
- No explicit performance benchmarks found yet

## Next Steps
1. Create dependency graph for text formatting modules
2. Design refactoring plan for large files
3. Create work packages for bug fixes
4. Establish performance benchmarks