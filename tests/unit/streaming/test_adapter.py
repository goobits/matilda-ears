"""Tests for SimulStreaming adapter with alpha/omega text separation."""

import numpy as np
import pytest

from matilda_ears.transcription.streaming import StreamingConfig, StreamingResult
from matilda_ears.transcription.streaming.internal.whisper_adapter import (
    StreamingAdapter,
    AlphaOmegaWrapper,
)


class TestStreamingConfig:
    """Test StreamingConfig dataclass."""

    def test_default_config(self):
        config = StreamingConfig()
        assert config.language == "en"
        assert config.model_size == "tiny"  # Optimized for CPU streaming
        assert config.frame_threshold == 25
        assert config.audio_max_len == 30.0
        assert config.segment_length == 1.0
        assert config.never_fire is True
        assert config.vad_enabled is True
        assert config.vad_threshold == 0.5

    def test_custom_config(self):
        config = StreamingConfig(
            language="de",
            model_size="medium",
            frame_threshold=30,
            never_fire=False,
        )
        assert config.language == "de"
        assert config.model_size == "medium"
        assert config.frame_threshold == 30
        assert config.never_fire is False


class TestStreamingResult:
    """Test StreamingResult dataclass."""

    def test_default_result(self):
        result = StreamingResult()
        assert result.alpha_text == ""
        assert result.omega_text == ""
        assert result.is_final is False
        assert result.audio_duration_seconds == 0.0

    def test_result_with_alpha_omega(self):
        result = StreamingResult(
            alpha_text="Hello world",
            omega_text="this is",
            is_final=False,
            audio_duration_seconds=2.5,
        )
        assert result.alpha_text == "Hello world"
        assert result.omega_text == "this is"
        assert result.is_final is False
        assert result.audio_duration_seconds == 2.5

    def test_final_result(self):
        result = StreamingResult(
            alpha_text="Complete transcription",
            omega_text="",
            is_final=True,
            audio_duration_seconds=10.0,
        )
        assert result.alpha_text == "Complete transcription"
        assert result.omega_text == ""
        assert result.is_final is True


class TestStreamingAdapter:
    """Test StreamingAdapter initialization and state."""

    def test_adapter_initialization(self):
        adapter = StreamingAdapter()
        assert adapter.is_initialized is False
        assert adapter.config.language == "en"
        assert adapter.config.model_size == "tiny"
        # Check coalescing state initialized
        assert adapter._vad is None  # Not loaded until start()
        assert adapter._dirty is False
        assert adapter._inference_running is False
        assert adapter._pending_audio == []

    def test_adapter_with_custom_config(self):
        config = StreamingConfig(language="fr", model_size="medium")
        adapter = StreamingAdapter(config)
        assert adapter.config.language == "fr"
        assert adapter.config.model_size == "medium"

    @pytest.mark.asyncio
    async def test_process_chunk_before_start_raises(self):
        adapter = StreamingAdapter()
        pcm = np.zeros(1600, dtype=np.int16)

        with pytest.raises(RuntimeError, match="not started"):
            await adapter.process_chunk(pcm)


class TestAlphaOmegaWrapper:
    """Test AlphaOmegaWrapper behavior with mock objects."""

    def test_wrapper_extracts_alpha_omega(self):
        """Test that wrapper correctly extracts alpha and omega text."""

        # Create a mock online processor that simulates the real behavior
        class MockModel:
            def __init__(self):
                self.tokenizer = type("Tokenizer", (), {"decode": lambda self, t: "test"})()

            def infer(self, is_last=False):
                # Return mock tokens and generation with truncated word
                return [], {
                    "result": {"split_words": [["hello"]], "split_tokens": [[1]]},
                    "result_truncated": {"split_words": [["world"]], "split_tokens": [[2]]},
                    "progress": [],
                }

        class MockOnline:
            def __init__(self):
                self.model = MockModel()
                self.audio_chunks = []

            def insert_audio_chunk(self, audio):
                self.audio_chunks.append(audio)

            def process_iter(self):
                # Simulate calling model.infer like the real code does
                self.model.infer()
                return {"text": "hello", "start": 0, "end": 1, "tokens": [], "words": []}

            def init(self, offset=None):
                self.audio_chunks = []

        online = MockOnline()
        wrapper = AlphaOmegaWrapper(online)

        # Insert some audio
        audio = np.zeros(1600, dtype=np.float32)
        wrapper.insert_audio_chunk(audio)

        # Process and check result - this will call the patched infer
        result = wrapper.process_iter()
        assert "alpha" in result
        assert "omega" in result
        assert result["alpha"] == "hello"
        # omega comes from result_truncated captured by patched infer
        assert result["omega"] == "world"

    def test_wrapper_init_resets_state(self):
        """Test that init() resets the wrapper state."""

        class MockModel:
            def infer(self, is_last=False):
                return [], {}

        class MockOnline:
            def __init__(self):
                self.model = MockModel()
                self.init_called = False

            def insert_audio_chunk(self, audio):
                pass

            def process_iter(self):
                return {}

            def init(self, offset=None):
                self.init_called = True

        online = MockOnline()
        wrapper = AlphaOmegaWrapper(online)

        wrapper.init()
        assert online.init_called is True
        assert wrapper._last_generation is None


class TestSessionResult:
    """Test SessionResult mapping from alpha/omega."""

    def test_session_result_maps_alpha_to_confirmed(self):
        from matilda_ears.transcription.streaming.session import SessionResult

        result = SessionResult(
            confirmed_text="stable text",
            tentative_text="unstable",
        )
        assert result.confirmed_text == "stable text"
        assert result.tentative_text == "unstable"


class TestStreamingSession:
    """Test StreamingSession interface."""

    def test_session_initialization(self):
        from matilda_ears.transcription.streaming.session import StreamingSession

        session = StreamingSession(session_id="test-123")
        assert session.session_id == "test-123"
        assert session.config.language == "en"

    def test_session_with_config(self):
        from matilda_ears.transcription.streaming.session import StreamingSession

        config = StreamingConfig(language="es", model_size="large-v3")
        session = StreamingSession(session_id="test-456", config=config)
        assert session.config.language == "es"
        assert session.config.model_size == "large-v3"
