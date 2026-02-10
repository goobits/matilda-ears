import os
import shutil
import tempfile
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

torch = pytest.importorskip("torch")

# Adjust import path as needed
# Using string imports inside patch where possible or direct imports
from matilda_ears.transcription.streaming.vendor.simul_whisper.simul_whisper import PaddedAlignAttWhisper
from matilda_ears.transcription.streaming.vendor.simul_whisper.generation_progress import Tokens, BeamTokens, Logits


def test_logdir_save_generation_progress():
    # Setup temp dir for logs
    temp_dir = tempfile.mkdtemp()

    try:
        # Mock dependencies
        cfg = MagicMock()
        cfg.logdir = temp_dir
        cfg.language = "en"
        cfg.model_path = "dummy.pt"
        cfg.decoder_type = "greedy"
        cfg.max_context_tokens = 100
        cfg.rewind_threshold = 10
        cfg.beam_size = 1
        cfg.audio_min_len = 0.1
        cfg.audio_max_len = 10.0
        cfg.static_init_prompt = None
        cfg.init_prompt = None

        # Patch load_model and other heavy lifting init calls
        with (
            patch(
                "matilda_ears.transcription.streaming.vendor.simul_whisper.simul_whisper.load_model"
            ) as mock_load_model,
            patch("matilda_ears.transcription.streaming.vendor.simul_whisper.simul_whisper.load_cif") as mock_load_cif,
            patch(
                "matilda_ears.transcription.streaming.vendor.simul_whisper.simul_whisper.tokenizer.get_tokenizer"
            ) as mock_get_tokenizer,
        ):

            # Setup mock model dimensions
            mock_model = MagicMock()
            mock_model.dims.n_text_ctx = 100
            mock_model.dims.n_audio_state = 80
            mock_model.decoder.blocks = []
            mock_model.alignment_heads.indices.return_value.T = []
            mock_model.num_languages = 10
            mock_model.device = torch.device("cpu")
            mock_load_model.return_value = mock_model

            mock_load_cif.return_value = (MagicMock(), False, False)

            mock_tokenizer = MagicMock()
            mock_tokenizer.decode.side_effect = lambda x: "".join([str(i) for i in x])  # simple mock decode
            mock_tokenizer.sot_sequence = [1, 2, 3]
            mock_tokenizer.sot_sequence_including_notimestamps = [1, 2, 3]
            mock_tokenizer.sot = 1
            mock_tokenizer.all_language_tokens = []
            mock_tokenizer.no_speech = None

            # Additional attributes needed for sort
            mock_tokenizer.transcribe = 50258
            mock_tokenizer.translate = 50259
            mock_tokenizer.sot_prev = 50260
            mock_tokenizer.sot_lm = 50261
            mock_tokenizer.no_timestamps = 50262
            mock_tokenizer.eot = 50257

            mock_get_tokenizer.return_value = mock_tokenizer

            whisper = PaddedAlignAttWhisper(cfg)
            whisper.tokenizer = mock_tokenizer  # explicit set to be sure

            # Prepare generation data
            generation = {
                "starting_tokens": BeamTokens(torch.tensor([1, 2, 3]), 1),
                "token_len_before_decoding": 3,
                "frames_len": 100,
                "frames_threshold": 4,
                "logits_starting": None,
                "no_speech_prob": 0.1,
                "no_speech": False,
                "progress": [
                    {
                        "logits_before_suppress": Logits(torch.zeros(1, 10)),
                        "beam_tokens": Tokens(torch.tensor([4, 5])),
                        "sum_logprobs": [0.5],
                        "completed": False,
                        "most_attended_frames": [10, 11],
                    }
                ],
            }

            # Input segments (dummy audio)
            input_segments = np.zeros((16000,), dtype=np.float32)
            new_hypothesis = [4, 5]

            # Call logdir_save
            whisper.logdir_save(input_segments, new_hypothesis, generation)

            # Check if file exists
            expected_dir = os.path.join(temp_dir, f"seg_{whisper.log_segments:05d}")
            expected_file = os.path.join(expected_dir, f"iter_{whisper.logdir_i:05d}_generation.txt")

            assert os.path.exists(expected_file), f"File {expected_file} not created"

            with open(expected_file) as f:
                content = f.read()
                print("Content of generation file:")
                print(content)

                assert "starting_tokens" in content
                assert "Progress:" in content
                assert "beam_tokens" in content

    finally:
        shutil.rmtree(temp_dir)
