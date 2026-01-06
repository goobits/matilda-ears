"""
Modal.com training script for custom wake word models.

This runs OpenWakeWord training on Modal's cloud GPUs.
Usage: modal run src/matilda_ears/wake_word/internal/modal_train.py --phrase "hey matilda"

Or via the ears CLI:
  ears train-wake-word "hey matilda"
"""

import modal

# Define the Modal app
app = modal.App("matilda-wake-word-trainer")

# Docker image with all dependencies
training_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg")  # Required for cloning OpenWakeWord and audio processing
    .pip_install(
        "openwakeword",
        "torch",
        "torchaudio",
        "onnx",
        "onnxruntime",
        "piper-tts",
        "numpy",
        "scipy",
        "pyyaml",
        "tqdm",
        "torchinfo",  # Required for OpenWakeWord training
        "torchmetrics",  # Required for OpenWakeWord training
        "mutagen",  # Audio metadata
        "tensorflow",  # Required by openwakeword training
        "pronouncing",  # Required for adversarial text generation
        "audiomentations",  # Required for audio augmentation
    )
)


@app.function(
    image=training_image,
    gpu="T4",  # Free tier GPU
    timeout=3600,  # 1 hour max
    memory=8192,  # 8GB RAM
)
def train_wake_word(
    phrase: str,
    num_samples: int = 3000,
    epochs: int = 10,
) -> bytes:
    """Train a wake word model and return the ONNX bytes."""
    import os
    import tempfile
    import subprocess
    from pathlib import Path

    print(f"=" * 60)
    print(f"Training wake word model for: {phrase}")
    print(f"Samples: {num_samples}, Epochs: {epochs}")
    print(f"=" * 60)

    # Normalize the phrase to a model name
    model_name = phrase.lower().replace(" ", "_").replace("-", "_")

    # Create working directory
    work_dir = Path(tempfile.mkdtemp())
    output_dir = work_dir / "output"
    output_dir.mkdir()

    # Clone OpenWakeWord
    print("\n[1/5] Setting up OpenWakeWord...")
    subprocess.run(
        ["git", "clone", "--depth=1", "https://github.com/dscripka/openWakeWord.git"],
        cwd=work_dir,
        capture_output=True,
    )

    oww_dir = work_dir / "openWakeWord"

    # Generate synthetic training data using piper-tts
    print("\n[2/5] Generating synthetic speech samples...")

    # Use OpenWakeWord's built-in synthetic data generation
    try:
        import sys
        sys.path.insert(0, str(oww_dir))

        from openwakeword.data import generate_clips

        # Generate positive samples
        positive_dir = output_dir / "positive"
        positive_dir.mkdir()

        generate_clips(
            text=phrase,
            output_dir=str(positive_dir),
            n_samples=num_samples,
        )
        print(f"Generated {num_samples} positive samples")

    except ImportError:
        # Fallback: Use piper directly
        print("Using piper-tts directly for sample generation...")
        positive_dir = output_dir / "positive"
        positive_dir.mkdir()

        # Install piper voices
        subprocess.run(
            ["pip", "install", "piper-tts"],
            capture_output=True,
        )

        # Generate samples with different voices
        voices = [
            "en_US-lessac-medium",
            "en_US-amy-medium",
            "en_GB-alba-medium",
        ]

        samples_per_voice = num_samples // len(voices)
        sample_idx = 0

        for voice in voices:
            for i in range(samples_per_voice):
                wav_path = positive_dir / f"sample_{sample_idx:05d}.wav"
                subprocess.run(
                    ["piper", "--model", voice, "--output_file", str(wav_path)],
                    input=phrase.encode(),
                    capture_output=True,
                )
                sample_idx += 1

        print(f"Generated {sample_idx} positive samples")

    # Generate negative samples (random speech without wake word)
    print("\n[3/5] Generating negative samples...")
    negative_dir = output_dir / "negative"
    negative_dir.mkdir()

    # Use adversarial phrases that sound similar
    adversarial_phrases = [
        phrase.replace("hey", "say"),
        phrase.replace("hey", "hay"),
        phrase.replace("hey", "he"),
        phrase.split()[-1] if len(phrase.split()) > 1 else "hello",
        "hello there",
        "what's the weather",
        "play some music",
        "turn on the lights",
    ]

    neg_samples_per_phrase = num_samples // (len(adversarial_phrases) * 2)
    neg_idx = 0

    for neg_phrase in adversarial_phrases:
        for i in range(neg_samples_per_phrase):
            wav_path = negative_dir / f"neg_{neg_idx:05d}.wav"
            subprocess.run(
                ["piper", "--model", "en_US-lessac-medium", "--output_file", str(wav_path)],
                input=neg_phrase.encode(),
                capture_output=True,
            )
            neg_idx += 1

    print(f"Generated {neg_idx} negative samples")

    # Train the model
    print("\n[4/5] Training neural network...")

    model_output_path = output_dir / f"{model_name}.onnx"

    # Use OpenWakeWord's training CLI which is more reliable
    train_result = subprocess.run(
        [
            "python", "-c", f"""
import os
import sys
sys.path.insert(0, '{oww_dir}')
os.chdir('{oww_dir}')

from openwakeword.train import train_model

# Run training
train_model(
    target_phrase='{phrase}',
    positive_audio_dir='{positive_dir}',
    negative_audio_dir='{negative_dir}',
    output_dir='{output_dir}',
    epochs={epochs},
    batch_size=64,
)
"""
        ],
        capture_output=True,
        text=True,
    )

    if train_result.stdout:
        print(f"Training stdout: {train_result.stdout}")
    if train_result.stderr:
        print(f"Training stderr: {train_result.stderr}")

    if train_result.returncode != 0:
        print(f"Training failed with code {train_result.returncode}")
        # Try alternative method using the module directly
        print("Trying alternative training method...")
        alt_result = subprocess.run(
            [
                "python", "-m", "openwakeword.train",
                "--target_phrase", phrase,
                "--positive_audio_dir", str(positive_dir),
                "--negative_audio_dir", str(negative_dir),
                "--output_dir", str(output_dir),
                "--epochs", str(epochs),
            ],
            capture_output=True,
            text=True,
        )
        if alt_result.stdout:
            print(f"Alt stdout: {alt_result.stdout}")
        if alt_result.stderr:
            print(f"Alt stderr: {alt_result.stderr}")

    # Find the output model
    print("\n[5/5] Exporting model...")

    onnx_files = list(output_dir.glob("**/*.onnx"))
    if not onnx_files:
        # Check if model was saved elsewhere
        onnx_files = list(work_dir.glob("**/*.onnx"))

    if onnx_files:
        model_path = onnx_files[0]
        print(f"Model saved: {model_path}")

        # Read and return the model bytes
        with open(model_path, "rb") as f:
            model_bytes = f.read()

        print(f"\n{'=' * 60}")
        print(f"SUCCESS! Model size: {len(model_bytes) / 1024 / 1024:.2f} MB")
        print(f"{'=' * 60}")

        return model_bytes
    else:
        raise RuntimeError("Training failed - no ONNX model produced")


@app.local_entrypoint()
def main(
    phrase: str = "hey matilda",
    output: str = None,
    samples: int = 3000,
    epochs: int = 10,
):
    """Train a wake word model.

    Args:
        phrase: The wake word phrase to train (e.g., "hey matilda")
        output: Output path for the ONNX file (default: {phrase}.onnx)
        samples: Number of training samples to generate
        epochs: Number of training epochs
    """
    from pathlib import Path

    # Determine output path
    model_name = phrase.lower().replace(" ", "_").replace("-", "_")
    if output is None:
        output = f"{model_name}.onnx"

    output_path = Path(output)

    print(f"Training wake word: '{phrase}'")
    print(f"Output: {output_path}")
    print()

    # Run training on Modal's GPU
    model_bytes = train_wake_word.remote(
        phrase=phrase,
        num_samples=samples,
        epochs=epochs,
    )

    # Save the model locally
    output_path.write_bytes(model_bytes)

    print(f"\n✓ Model saved to: {output_path}")
    print(f"\nTo use it:")
    print(f"  1. Move to: matilda-ears/src/matilda_ears/wake_word/models/{model_name}.onnx")
    print(f"  2. Run: ears --wake-word --agent-aliases=\"Matilda:{model_name}\"")
