# STREAMING TRANSCRIPTION IMPLEMENTATION CHECKLIST

## What We Already Have ✅
- ✅ **Silero VAD with hysteresis** (`src/modes/conversation.py:96-122`)
- ✅ **Robust audio streaming** (`src/audio/audio_streamer.py`, `src/audio/capture.py`)
- ✅ **Async processing architecture** (`src/modes/conversation.py:69-94`)
- ✅ **WebSocket integration** (`src/transcription/server.py`)
- ✅ **Opus encoding/decoding** (`src/audio/encoder.py`, `src/audio/decoder.py`)

## Implementation Strategy (Revised Order) 🚧

### Phase 0: Foundation (MVP - Start Here!)
- [ ] **Add result storage** - Store previous transcription result in conversation mode
- [ ] **Basic comparison logic** - Simple string comparison (current vs previous)
- [ ] **Partial emission during speech** - Send partial results while VAD detects speech
- [ ] **Test with existing system** - Validate approach without major architectural changes

**Phase 0 Test:** Record 10-second speech sample, verify partial transcription results appear within 2 seconds of speech start (before speech ends). Measure: time from speech start to first partial result.

### Phase 1: Core Streaming Logic  
- [ ] **Change processing model** - Process chunks during speech (not after utterance completion)
- [ ] **Implement LocalAgreement-2** - Only emit text confirmed by 2 consecutive Whisper runs
- [ ] **Simple context buffer** - Keep last 2-3 seconds of audio for transcription accuracy
- [ ] **Modify `_conversation_loop()`** - Add chunk processing during VAD speech detection

**Phase 1 Test:** Speak "Hello world" twice with 1-second pause between. Verify "Hello" appears as confirmed only after both runs agree, but wrong partial words don't get confirmed. Measure: agreement accuracy rate.

### Phase 2: Smart Buffering & Context
- [ ] **Sliding window management** - Maintain context without infinite buffer growth
- [ ] **VAD-guided trimming** - Use existing Silero VAD to find sentence boundaries  
- [ ] **Define confidence levels** - `confirmed`, `provisional`, `pending` states
- [ ] **Context preservation** - Use last 200 words as Whisper prompt parameter

**Phase 2 Test:** Speak 60-second continuous monologue with natural pauses. Verify buffer never exceeds 30 seconds, trimming happens at sentence boundaries, and confidence levels are correctly assigned. Measure: buffer size over time + confidence accuracy.

### Phase 3: Advanced Features
- [ ] **Interruption handling** - Process new speech during active transcription
- [ ] **Timestamp validation** - Skip redundant processing within 1-second intervals
- [ ] **Advanced agreement scoring** - N-grams matching, Levenshtein distance
- [ ] **Multi-level confidence display** - Different styling for confidence levels

**Phase 3 Test:** Start speaking, then interrupt mid-sentence with new speech. Verify system gracefully handles interruption, processes new speech immediately, and doesn't lose context. Measure: interruption response time + context preservation accuracy.

### Phase 4: Integration & Optimization
- [ ] **Performance tuning** - Optimize chunk sizes, buffer management, latency
- [ ] **Update text formatting** - Support partial/provisional formatting states
- [ ] **Add streaming configuration** - Tunable parameters for different use cases
- [ ] **Comprehensive testing** - Latency, accuracy, reliability validation

**Phase 4 Test:** 10-minute natural conversation with multiple speakers, technical terms, and entity formatting (numbers, dates, URLs). Verify <4s average latency, proper text formatting on streaming results, and <2% accuracy degradation vs batch mode. Measure: end-to-end performance metrics.

## Key Implementation Insight
**Start small**: The minimal change is processing audio chunks **during speech detection** (in `_conversation_loop()` lines 156-170) instead of waiting for complete utterances. This alone enables partial results with minimal architectural changes.

## Technical Architecture

### Phase 0: Minimal Changes (Start Here)
**Modified Components:**
- `src/modes/conversation.py:_conversation_loop()` - Add chunk processing during speech
- `src/modes/conversation.py:_process_utterance()` - Store previous results, emit partial text

### Phase 1+: New Components (Later)
```
src/transcription/
├── streaming_engine.py      # LocalAgreement-2 + confidence scoring
├── buffer_manager.py        # Sliding window with context preservation  
└── realtime_formatter.py    # Streaming text formatting integration
```

### Configuration Parameters
```json
{
  "streaming": {
    "enable_partial_results": true,
    "chunk_processing_interval_ms": 500,
    "agreement_threshold": 2,
    "context_window_s": 3,
    "max_buffer_duration_s": 30,
    "confidence_levels": ["confirmed", "provisional", "pending"]
  }
}
```

## Implementation Approach

### Critical Code Locations
- **`_conversation_loop()` (line 156-170)** - Where VAD detects speech, add chunk processing
- **`_process_utterance()` (line 212-237)** - Currently waits for complete utterance, modify for streaming
- **`_transcribe_audio_with_vad_stats()` (line 239)** - Add result comparison and agreement logic

### Expected Performance
- **Phase 0**: Partial results within 1-2 seconds, minimal accuracy loss
- **Phase 1+**: ~3-4 seconds latency, 2-6% WER increase vs offline
- **Reliability**: Significantly reduced text flickering after Phase 1

## Success Criteria by Phase
**Phase 0:**
- ✅ Partial transcription results during speech
- ✅ No major architectural disruption

**Phase 1+:**
- ✅ Stable confirmed text (no flickering)
- ✅ Real-time streaming with <4s latency  
- ✅ Ready for STT→TTS pipeline integration

## Implementation Timeline
1. **Week 1**: Phase 0 MVP - partial results during speech
2. **Week 2**: Phase 1 - LocalAgreement-2 + basic context buffer
3. **Week 3**: Phase 2 - smart buffering + confidence levels
4. **Week 4**: Phase 3 - advanced features + optimization

---
*Revised approach: Start with minimal changes to prove concept, then build sophisticated streaming engine on proven foundation.*