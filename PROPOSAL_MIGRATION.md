# GOOBITS STT Directory Structure Migration Proposal

## Overview
This proposal outlines a comprehensive directory structure refactor to improve code organization, eliminate redundancy, and enhance maintainability following the successful Phase 3.5 pivot to markdown-first architecture.

## Current State Analysis

### Issues Identified
- ❌ **Backup files**: Leftover pivot files cluttering document_parsing/
- ❌ **Redundant emotion detectors**: Basic and advanced doing similar work
- ❌ **Misplaced configuration**: config.json in src/ instead of core/
- ❌ **Scattered utilities**: Single-file utils/ directory
- ❌ **Non-code directories in src/**: logs/ and shared-setup/ don't belong
- ❌ **Generic file names**: capture.py, decoder.py lack specificity

## Proposed Migration Plan

### Phase 1: Cleanup and Consolidation

#### 1.1 Remove Backup Files
```bash
rm src/document_parsing/parser_factory_backup.py
rm src/document_parsing/parser_factory_new.py
```

#### 1.2 Consolidate Emotion Detection
```bash
# Remove basic emotion detector (functionality preserved in advanced)
rm src/speech_synthesis/emotion_detector.py

# Rename advanced to primary
mv src/speech_synthesis/advanced_emotion_detector.py src/speech_synthesis/emotion_detector.py
```

#### 1.3 Relocate Configuration
```bash
mv src/config.json src/core/config.json
```

### Phase 2: Directory Restructuring

#### 2.1 Move Non-Code Directories to Root
```bash
mv src/logs/ ./logs/
mv src/shared-setup/ ./setup/
```

#### 2.2 Consolidate Utils
```bash
mv src/utils/ssl.py src/transcription/ssl_utils.py
rmdir src/utils/
```

#### 2.3 Rename Performance Cache
```bash
mv src/document_parsing/performance_cache.py src/document_parsing/document_cache.py
```

### Phase 3: File Naming Improvements

#### 3.1 Audio Module Specificity
```bash
mv src/audio/capture.py src/audio/audio_capture.py
mv src/audio/decoder.py src/audio/opus_decoder.py
mv src/audio/encoder.py src/audio/opus_encoder.py
```

## Target Directory Structure

```
project_root/
├── src/
│   ├── audio/
│   │   ├── audio_capture.py          ← capture.py
│   │   ├── audio_streamer.py
│   │   ├── opus_decoder.py           ← decoder.py
│   │   ├── opus_encoder.py           ← encoder.py
│   │   ├── opus_batch.py
│   │   └── vad.py
│   ├── core/
│   │   ├── config.py
│   │   └── config.json               ← src/config.json
│   ├── document_parsing/
│   │   ├── base_parser.py
│   │   ├── document_cache.py         ← performance_cache.py
│   │   ├── markdown_parser.py
│   │   ├── parser_factory.py
│   │   └── universal_converter.py
│   ├── integration/
│   │   └── mixed_content_processor.py
│   ├── modes/
│   │   ├── base_mode.py
│   │   ├── conversation.py
│   │   ├── hold_to_talk.py
│   │   ├── listen_once.py
│   │   └── tap_to_talk.py
│   ├── speech_synthesis/
│   │   ├── emotion_detector.py       ← advanced_emotion_detector.py
│   │   ├── semantic_formatter.py
│   │   ├── speech_markdown.py
│   │   ├── ssml_generator.py
│   │   └── tts_engine.py
│   ├── text_formatting/
│   │   ├── detectors/
│   │   ├── resources/
│   │   └── [existing files]
│   ├── transcription/
│   │   ├── client.py
│   │   ├── server.py
│   │   ├── streaming.py
│   │   └── ssl_utils.py              ← utils/ssl.py
│   └── main.py
├── logs/                             ← src/logs/
├── setup/                            ← src/shared-setup/
└── [project files]
```

## Import Updates Required

### Files Requiring Import Changes

#### main.py
```python
# OLD
from src.speech_synthesis.advanced_emotion_detector import AdvancedEmotionDetector
from src.document_parsing.performance_cache import PerformanceOptimizer

# NEW  
from src.speech_synthesis.emotion_detector import AdvancedEmotionDetector
from src.document_parsing.document_cache import PerformanceOptimizer
```

#### mixed_content_processor.py
```python
# OLD
from src.speech_synthesis.emotion_detector import ContentEmotionDetector

# NEW
from src.speech_synthesis.emotion_detector import AdvancedEmotionDetector
```

#### Any files importing audio modules
```python
# OLD
from src.audio.capture import AudioCapture
from src.audio.decoder import OpusDecoder

# NEW
from src.audio.audio_capture import AudioCapture  
from src.audio.opus_decoder import OpusDecoder
```

#### Any files importing ssl utilities
```python
# OLD
from src.utils.ssl import create_ssl_context

# NEW
from src.transcription.ssl_utils import create_ssl_context
```

## Benefits

### Immediate Benefits
- ✅ **Cleaner codebase**: Remove 5 unnecessary backup/duplicate files
- ✅ **Better organization**: Logical grouping of related functionality
- ✅ **Clearer naming**: More descriptive file names
- ✅ **Reduced complexity**: Single emotion detector instead of two
- ✅ **Proper separation**: Code vs non-code directories

### Long-term Benefits  
- ✅ **Easier maintenance**: Clear file purposes and locations
- ✅ **Better onboarding**: Intuitive directory structure
- ✅ **Reduced confusion**: No duplicate/backup files
- ✅ **Scalability**: Well-organized foundation for future features

## Risk Assessment

### Low Risk Changes
- File renames (no logic changes)
- Directory moves (structure only)
- Backup file removal (already superseded)

### Medium Risk Changes
- Emotion detector consolidation (requires import updates)
- Config file relocation (may need path updates)

### Mitigation Strategy
1. **Test before migration**: Verify current functionality works
2. **Phase implementation**: Do changes in logical groups
3. **Test after each phase**: Ensure no regressions
4. **Update imports systematically**: Use grep to find all references

## Success Criteria

### Verification Steps
1. **All tests pass**: No functionality regressions
2. **Import resolution**: No broken import statements
3. **CLI functionality**: All document processing modes work
4. **Phase 4 features**: SSML, emotion detection, caching operational
5. **Clean structure**: No orphaned files or empty directories

### File Count Reduction
- **Before**: ~50+ files across multiple directories
- **After**: ~45 files with improved organization
- **Eliminated**: 5+ backup/duplicate files

## Implementation Timeline

### Phase 1 (Low Risk - 30 minutes)
- Remove backup files
- Move non-code directories
- Consolidate utils

### Phase 2 (Medium Risk - 45 minutes)  
- Rename files
- Move config.json
- Update imports

### Phase 3 (Verification - 30 minutes)
- Test all CLI modes
- Verify Phase 4 features
- Validate import resolution

**Total Estimated Time: 2 hours**

## Approval Required

This migration requires approval for:
1. **File deletions**: Backup files and basic emotion detector
2. **Directory restructuring**: Moving logs/, setup/, utils/
3. **Import updates**: Multiple files require import path changes
4. **Testing verification**: Comprehensive testing after migration

---

**Recommendation**: Proceed with migration to achieve cleaner, more maintainable codebase structure that better reflects the current architecture following the successful Phase 3.5 pivot.