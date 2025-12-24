# Feature: Text Transformation Personalities

## Overview
Add configurable "personalities" that transform transcribed text through local TTT processing before final output.

## Workflow
1. User activates hotkey (Matilda)
2. Speech is transcribed (STT)
3. **[NEW]** Transcription passes through local TTT with personality prompt
4. Transformed text output (optionally to TTS)

## Example Use Case
**Pirate Speak Personality**
- Input (transcribed): "Hello, how are you doing today?"
- TTT Transformation: Convert to pirate speak
- Output: "Ahoy, how be ye farin' this fine day?"

## Implementation Notes
- Use local TTT backend (Ollama) to avoid API costs
- Personalities defined as system prompts/templates
- Configurable per-session or persistent setting
- Should be optional/toggleable (default: off)

## Potential Personalities
- Pirate speak
- Formal/professional
- Casual/slang
- Shakespearean
- ELI5 (explain like I'm 5)
- Technical jargon enhancement
- Custom user-defined

## Configuration
```yaml
# Possible config structure
personalities:
  enabled: true
  active: "pirate"
  definitions:
    pirate:
      prompt: "Convert the following text to pirate speak, maintaining the core meaning..."
      model: "llama2"  # local model
    formal:
      prompt: "Rewrite the following text in formal professional language..."
      model: "llama2"
```

## Integration Point
- **Primary**: Matilda integration layer (workflow orchestration)
- **Alternative**: STT post-processing hook (if keeping STT-specific)
- Uses existing TTT local backend infrastructure

## Status
**PROPOSED** - Feature request from management
Not yet implemented

## Notes
- This is a mandatory requirement from higher up
- Focus on local TTT to keep it free/fast
- Should work seamlessly in the voice assistant workflow
