#!/usr/bin/env python3
"""
Matilda Wake Word Training Script for Google Colab

USAGE:
1. Open Google Colab: https://colab.research.google.com
2. Create a new notebook (File > New notebook)
3. Copy this ENTIRE script into a cell
4. Change TARGET_PHRASE below to your wake word
5. Run the cell (Shift+Enter)
6. Wait ~30-60 minutes
7. Model will auto-download when complete

The output file (e.g., hey_matilda.onnx) should be placed in:
  matilda-ears/src/matilda_ears/wake_word/models/
"""

# ============================================================================
# CONFIGURE YOUR WAKE WORD HERE
# ============================================================================

TARGET_PHRASE = "hey matilda"  # <-- CHANGE THIS TO YOUR WAKE WORD

# Optional: Additional phrases to train (same model responds to all)
# ADDITIONAL_PHRASES = ["matilda", "hey assistant"]
ADDITIONAL_PHRASES = []

# Optional: Adjust these if needed
NUM_SAMPLES = 5000        # More = better accuracy, slower training
THRESHOLD = 0.5           # Detection threshold (0.3-0.7 typical)
EPOCHS = 10               # Training epochs

# ============================================================================
# AUTOMATIC SETUP - DO NOT MODIFY BELOW THIS LINE
# ============================================================================

import subprocess
import sys
import os

def run(cmd):
    """Run shell command and print output."""
    print(f">>> {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode == 0

print("=" * 60)
print(f"Training wake word model for: {TARGET_PHRASE}")
print("=" * 60)

# Step 1: Install dependencies
print("\n[1/6] Installing dependencies...")
run("pip install -q openwakeword torch torchaudio onnx onnxruntime")
run("pip install -q piper-tts")  # For synthetic speech generation

# Step 2: Import libraries
print("\n[2/6] Loading libraries...")
try:
    import numpy as np
    import torch
    from pathlib import Path
    import json
    import yaml
    import tempfile
    import shutil
except ImportError as e:
    print(f"Import error: {e}")
    print("Retrying installations...")
    run("pip install numpy torch pyyaml")
    import numpy as np
    import torch
    from pathlib import Path
    import json
    import yaml
    import tempfile
    import shutil

# Check for GPU
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")
if device == "cpu":
    print("WARNING: No GPU detected. Training will be slower.")

# Step 3: Create working directory
print("\n[3/6] Setting up workspace...")
work_dir = Path("/content/wake_word_training")
work_dir.mkdir(exist_ok=True)
os.chdir(work_dir)

# Clone OpenWakeWord if not present
if not (work_dir / "openWakeWord").exists():
    run("git clone https://github.com/dscripka/openWakeWord.git")

sys.path.insert(0, str(work_dir / "openWakeWord"))

# Step 4: Generate training config
print("\n[4/6] Creating training configuration...")

model_name = TARGET_PHRASE.lower().replace(" ", "_").replace("-", "_")
all_phrases = [TARGET_PHRASE] + ADDITIONAL_PHRASES

config = {
    "target_phrase": all_phrases if len(all_phrases) > 1 else TARGET_PHRASE,
    "model_name": model_name,
    "n_samples": NUM_SAMPLES,
    "n_epochs": EPOCHS,
    "output_dir": str(work_dir / "output"),
    "batch_size": 256 if device == "cuda" else 64,

    # TTS settings for synthetic data generation
    "tts_engine": "piper",
    "piper_models": [
        "en_US-lessac-medium",
        "en_US-libritts-high",
        "en_GB-cori-medium",
    ],

    # Augmentation settings
    "augmentation": {
        "noise_levels": [0.0, 0.1, 0.2, 0.3],
        "room_sizes": ["small", "medium", "large"],
        "speed_variations": [0.9, 1.0, 1.1],
    },

    # Model settings
    "model": {
        "n_classes": 1,
        "custom_verifier_model": None,
        "custom_verifier_threshold": THRESHOLD,
    }
}

config_path = work_dir / "training_config.yaml"
with open(config_path, "w") as f:
    yaml.dump(config, f)

print(f"Config saved to: {config_path}")

# Step 5: Run training
print("\n[5/6] Training model (this takes 30-60 minutes)...")
print("=" * 60)

try:
    # Try using the automated training script
    from openWakeWord import train

    # Generate synthetic clips
    print("\nGenerating synthetic speech samples...")
    run(f"cd {work_dir}/openWakeWord && python -m openwakeword.train "
        f"--training_config {config_path} --generate_clips")

    # Augment clips
    print("\nAugmenting audio with noise and room acoustics...")
    run(f"cd {work_dir}/openWakeWord && python -m openwakeword.train "
        f"--training_config {config_path} --augment_clips")

    # Train model
    print("\nTraining neural network...")
    run(f"cd {work_dir}/openWakeWord && python -m openwakeword.train "
        f"--training_config {config_path} --train_model")

except Exception as e:
    print(f"Note: Using fallback training method due to: {e}")

    # Fallback: Use the notebook's training approach
    print("\nRunning alternative training pipeline...")

    # This is a simplified version - the full pipeline is in the notebook
    run(f"""
    cd {work_dir}/openWakeWord && python -c "
from openwakeword.utils import train_custom_model
train_custom_model(
    target_phrase='{TARGET_PHRASE}',
    output_dir='{work_dir}/output',
    n_samples={NUM_SAMPLES},
    epochs={EPOCHS}
)
"
    """)

# Step 6: Export and download
print("\n[6/6] Exporting model...")

output_dir = work_dir / "output"
onnx_files = list(output_dir.glob("**/*.onnx")) if output_dir.exists() else []

if onnx_files:
    # Find the best model
    onnx_path = onnx_files[0]
    final_name = f"{model_name}.onnx"
    final_path = work_dir / final_name

    shutil.copy(onnx_path, final_path)

    print("=" * 60)
    print(f"SUCCESS! Model saved to: {final_path}")
    print("=" * 60)

    # Auto-download in Colab
    try:
        from google.colab import files
        print(f"\nDownloading {final_name}...")
        files.download(str(final_path))
        print("\nDone! Place the downloaded file in:")
        print("  matilda-ears/src/matilda_ears/wake_word/models/")
    except ImportError:
        print(f"\nNot running in Colab. Model is at: {final_path}")

else:
    print("=" * 60)
    print("WARNING: No ONNX model found in output directory.")
    print("Check the training logs above for errors.")
    print("=" * 60)

    # List what we do have
    if output_dir.exists():
        print("\nFiles in output directory:")
        for f in output_dir.rglob("*"):
            print(f"  {f}")

print("\n" + "=" * 60)
print("NEXT STEPS:")
print("=" * 60)
print(f"1. Place {model_name}.onnx in:")
print("   matilda-ears/src/matilda_ears/wake_word/models/")
print(f"2. Use it: ears --wake-word --agent-aliases=\"Matilda:{model_name}\"")
print("=" * 60)
