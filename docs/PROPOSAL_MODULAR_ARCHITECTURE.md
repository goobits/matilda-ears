# PROPOSAL: Modular Voice Processing Ecosystem

**Status:** Draft  
**Date:** 2025-07-21  
**Author:** GOOBITS Team  

## Executive Summary

Transform the current monolithic voice assistant demo into a modular ecosystem of independent but interoperable Python packages. This architecture will enable better maintainability, reusability, and deployment flexibility while preserving the integrated user experience.

## Current State Analysis

### Problems with Current Architecture
- **CLI Dependencies**: External subprocess calls to `ttt` and `tts` commands
- **Deployment Complexity**: Multiple tools to install and configure
- **Performance Overhead**: Process spawning for each AI/TTS request
- **Tight Coupling**: Demo assumes all components are available
- **Limited Reusability**: Components can't be used independently

### Current Integration Flow
```
smart-voice-demo
├── subprocess("ttt", text) -> AI response
├── subprocess("tts", response) -> audio
└── STT processing (internal)
```

## Proposed Modular Architecture

### Core Philosophy
- **Independence**: Each package works standalone
- **Interoperability**: Clean integration points when combined
- **Optional Dependencies**: No forced coupling
- **Plugin Architecture**: Discoverable integrations

### Package Structure

#### 1. GOOBITS-STT (Speech-to-Text Core)
```
goobits-stt/
├── src/stt/
│   ├── core/              # VAD, Whisper, audio processing
│   ├── modes/             # conversation, tap-to-talk, etc.
│   ├── formats/           # text formatting engine
│   └── server/            # WebSocket server
├── src/integrations/      # Optional integration adapters
│   ├── ai_integration.py  # TTT integration
│   ├── tts_integration.py # TTS integration
│   └── base.py           # Integration interface
└── examples/
    ├── basic_stt.py      # STT-only demo
    └── smart_assistant.py # Full-featured demo
```

#### 2. GOOBITS-TTT (AI Text Processing)
```
goobits-ttt/
├── ttt_core/
│   ├── clients/          # OpenRouter, local models, etc.
│   ├── context/          # Conversation management
│   ├── models/           # Model abstractions
│   └── streaming/        # Real-time processing
├── ttt_cli/              # CLI wrapper (backward compatibility)
└── integrations/
    └── stt_plugin.py     # STT integration helpers
```

#### 3. GOOBITS-TTS (Text-to-Speech)
```
goobits-tts/
├── tts_core/
│   ├── engines/          # Edge TTS, local engines, etc.
│   ├── voices/           # Voice management
│   ├── streaming/        # Real-time synthesis
│   └── effects/          # Audio processing
├── tts_cli/              # CLI wrapper (backward compatibility)
└── integrations/
    └── stt_plugin.py     # STT integration helpers
```

## Integration Architecture

### Option 1: Optional Dependencies
```toml
# goobits-stt pyproject.toml
[project.optional-dependencies]
ai = ["goobits-ttt>=1.0.0"]
speech = ["goobits-tts>=1.0.0"]
full = ["goobits-ttt>=1.0.0", "goobits-tts>=1.0.0"]
demo = ["goobits-ttt>=1.0.0", "goobits-tts>=1.0.0", "pygame>=2.1.0"]
```

### Option 2: Plugin Discovery
```python
# src/integrations/discovery.py
def discover_ai_integration():
    """Dynamically discover available AI backends."""
    try:
        from ttt_core import TTTClient
        return TTTIntegration(TTTClient())
    except ImportError:
        return None

def discover_tts_integration():
    """Dynamically discover available TTS engines."""
    try:
        from tts_core import TTSEngine
        return TTSIntegration(TTSEngine())
    except ImportError:
        return None
```

### Integration Interface
```python
# src/integrations/base.py
class AIIntegration(ABC):
    @abstractmethod
    async def process_text(self, text: str, context: dict = None) -> str:
        pass

class TTSIntegration(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice: str = None) -> bytes:
        pass
    
    @abstractmethod
    def set_interruption_callback(self, callback):
        pass
```

## Migration Strategy

### Phase 1: Package Separation (Week 1-2)
1. Extract TTT functionality into `goobits-ttt` package
2. Extract TTS functionality into `goobits-tts` package
3. Maintain CLI compatibility for backward compatibility
4. Create Python API interfaces for each package

### Phase 2: Integration Layer (Week 3)
1. Implement integration adapters in `goobits-stt`
2. Add optional dependency management
3. Create unified configuration system
4. Implement plugin discovery mechanism

### Phase 3: Demo Refactoring (Week 4)
1. Refactor smart voice demo to use Python APIs
2. Add graceful fallbacks for missing components
3. Create installation variants (minimal, full, etc.)
4. Update documentation and examples

### Phase 4: Advanced Features (Week 5-6)
1. Shared memory optimization for integrated deployments
2. Streaming interfaces between components
3. Advanced configuration management
4. Performance monitoring and metrics

## Benefits

### For Developers
- **Modular Development**: Work on components independently
- **Easy Testing**: Unit test each package separately
- **Clear Interfaces**: Well-defined integration points
- **Flexible Deployment**: Choose components as needed

### For Users
- **Lightweight Installs**: Install only what you need
- **Better Performance**: No subprocess overhead when integrated
- **Easier Configuration**: Unified config when components are combined
- **Backward Compatibility**: Existing CLI tools continue working

### For Production
- **Simplified Deployment**: Single package with optional components
- **Better Error Handling**: Native Python exceptions vs CLI parsing
- **Resource Sharing**: Shared models and memory when appropriate
- **Monitoring**: Unified logging and metrics

## Installation Examples

```bash
# Minimal STT only
pip install goobits-stt

# STT with AI processing
pip install goobits-stt[ai]

# Full voice assistant
pip install goobits-stt[full]

# Development setup
pip install goobits-stt[dev,full]

# Individual components
pip install goobits-ttt  # AI processing only
pip install goobits-tts  # TTS only

# Legacy CLI tools (for existing scripts)
pip install goobits-ttt[cli] goobits-tts[cli]
```

## API Examples

### STT-Only Usage
```python
from goobits_stt import ConversationMode

mode = ConversationMode()
async for result in mode.listen():
    print(f"Transcribed: {result.text}")
```

### Integrated Voice Assistant
```python
from goobits_stt import SmartConversationMode

# Auto-discovers available AI and TTS components
mode = SmartConversationMode()
await mode.run()  # Full voice assistant with AI and speech synthesis
```

### Manual Integration
```python
from goobits_stt import ConversationMode
from goobits_ttt import TTTClient
from goobits_tts import TTSEngine

stt = ConversationMode()
ai = TTTClient(model="claude")
tts = TTSEngine(voice="en-US-AriaNeural")

async for result in stt.listen():
    response = await ai.process(result.text)
    audio = await tts.synthesize(response)
    # Play audio...
```

## Risk Assessment

### Low Risk
- Package separation (well-defined boundaries)
- Optional dependency management (standard Python practice)
- Backward compatibility maintenance

### Medium Risk
- Plugin discovery complexity
- Integration testing across packages
- Documentation coordination

### High Risk
- Performance regression during migration
- Breaking changes for existing users
- Coordination across multiple repositories

## Success Metrics

- **Installation Simplicity**: Single command installs for common use cases
- **Performance**: <10% overhead compared to current CLI approach
- **Adoption**: Developers use individual packages in other projects
- **Maintenance**: Reduced complexity in each package
- **User Experience**: Seamless integration when all components installed

## Timeline

- **Week 1-2**: Package separation and CLI compatibility
- **Week 3**: Integration layer implementation
- **Week 4**: Demo refactoring and testing
- **Week 5-6**: Advanced features and optimization
- **Week 7**: Documentation and release preparation

## Conclusion

This modular architecture transforms the GOOBITS ecosystem from a monolithic demo into a flexible, reusable set of voice processing components. Each package can stand alone or integrate seamlessly, providing maximum flexibility for users while maintaining the integrated experience for those who want it.

The approach follows Python best practices for package design and dependency management, ensuring long-term maintainability and broad adoption potential.