"""Model downloader with progress tracking.

Downloads Whisper models from Hugging Face with real-time progress callbacks.
Designed for integration with Tauri frontend for visual progress display.
"""

import json
import sys
from pathlib import Path
from typing import Callable, Optional

# Model configurations matching faster-whisper
WHISPER_MODELS = {
    "tiny": "Systran/faster-whisper-tiny",
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "base": "Systran/faster-whisper-base",
    "base.en": "Systran/faster-whisper-base.en",
    "small": "Systran/faster-whisper-small",
    "small.en": "Systran/faster-whisper-small.en",
    "medium": "Systran/faster-whisper-medium",
    "medium.en": "Systran/faster-whisper-medium.en",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "Systran/faster-whisper-large-v3-turbo",
}

# Approximate model sizes in MB for progress estimation
MODEL_SIZES_MB = {
    "tiny": 75,
    "tiny.en": 75,
    "base": 145,
    "base.en": 145,
    "small": 465,
    "small.en": 465,
    "medium": 1500,
    "medium.en": 1500,
    "large-v2": 3100,
    "large-v3": 3100,
    "large-v3-turbo": 1600,
}


def get_cache_dir() -> Path:
    """Get the Hugging Face cache directory."""
    try:
        from huggingface_hub import constants
        return Path(constants.HF_HUB_CACHE)
    except ImportError:
        # Fallback to default location
        return Path.home() / ".cache" / "huggingface" / "hub"


def is_model_cached(model_name: str) -> bool:
    """Check if a model is already downloaded."""
    if model_name not in WHISPER_MODELS:
        return False

    repo_id = WHISPER_MODELS[model_name]
    cache_dir = get_cache_dir()

    # Check for model directory in cache
    # Format: models--{org}--{repo}
    repo_cache_name = f"models--{repo_id.replace('/', '--')}"
    model_cache_path = cache_dir / repo_cache_name

    if model_cache_path.exists():
        # Check for model.bin or model files
        snapshots_dir = model_cache_path / "snapshots"
        if snapshots_dir.exists():
            for snapshot in snapshots_dir.iterdir():
                if (snapshot / "model.bin").exists():
                    return True
    return False


def download_model(
    model_name: str = "base",
    progress_callback: Optional[Callable[[dict], None]] = None,
    force: bool = False,
) -> bool:
    """Download a Whisper model with progress tracking.

    Args:
        model_name: Name of the model (tiny, base, small, medium, large-v3-turbo)
        progress_callback: Callback function receiving progress dict:
            {"status": "downloading", "progress": 0.5, "downloaded_mb": 72, "total_mb": 145}
        force: Force re-download even if cached

    Returns:
        True if download successful, False otherwise
    """
    if model_name not in WHISPER_MODELS:
        if progress_callback:
            progress_callback({
                "status": "error",
                "error": f"Unknown model: {model_name}. Available: {', '.join(WHISPER_MODELS.keys())}"
            })
        return False

    # Check cache first
    if not force and is_model_cached(model_name):
        if progress_callback:
            progress_callback({
                "status": "cached",
                "model": model_name,
                "message": f"Model {model_name} already downloaded"
            })
        return True

    repo_id = WHISPER_MODELS[model_name]
    total_size_mb = MODEL_SIZES_MB.get(model_name, 100)

    if progress_callback:
        progress_callback({
            "status": "starting",
            "model": model_name,
            "repo_id": repo_id,
            "estimated_size_mb": total_size_mb,
        })

    try:
        from huggingface_hub import snapshot_download
        from huggingface_hub.utils import tqdm as hf_tqdm

        # Track progress across all files
        downloaded_bytes = 0
        total_bytes = total_size_mb * 1024 * 1024  # Estimate

        class ProgressTracker:
            def __init__(self):
                self.downloaded = 0
                self.total = total_bytes
                self.last_progress = -1

            def update(self, n):
                self.downloaded += n
                progress = min(self.downloaded / self.total, 0.99)  # Cap at 99% until complete
                # Only report every 1% to reduce noise
                progress_int = int(progress * 100)
                if progress_int > self.last_progress:
                    self.last_progress = progress_int
                    if progress_callback:
                        progress_callback({
                            "status": "downloading",
                            "model": model_name,
                            "progress": progress,
                            "downloaded_mb": round(self.downloaded / (1024 * 1024), 1),
                            "total_mb": total_size_mb,
                        })

        tracker = ProgressTracker()

        # Monkey-patch tqdm to capture progress
        original_tqdm = hf_tqdm.tqdm

        class ProgressTqdm(original_tqdm):
            def update(self, n=1):
                super().update(n)
                tracker.update(n)

        hf_tqdm.tqdm = ProgressTqdm

        try:
            # Download the model
            snapshot_download(
                repo_id=repo_id,
                repo_type="model",
                local_files_only=False,
            )
        finally:
            # Restore original tqdm
            hf_tqdm.tqdm = original_tqdm

        if progress_callback:
            progress_callback({
                "status": "complete",
                "model": model_name,
                "progress": 1.0,
                "message": f"Model {model_name} downloaded successfully"
            })

        return True

    except ImportError as e:
        if progress_callback:
            progress_callback({
                "status": "error",
                "error": f"huggingface_hub not installed: {e}"
            })
        return False
    except Exception as e:
        if progress_callback:
            progress_callback({
                "status": "error",
                "error": str(e)
            })
        return False


def download_with_json_output(model_name: str = "base", force: bool = False) -> bool:
    """Download model with JSON progress output to stdout.

    Each line is a JSON object with progress information.
    Designed for parsing by Tauri or other frontend.
    """
    def json_callback(data: dict):
        print(json.dumps(data), flush=True)

    return download_model(model_name, progress_callback=json_callback, force=force)


def list_available_models() -> dict:
    """List all available models with their cache status."""
    models = {}
    for name in WHISPER_MODELS:
        models[name] = {
            "repo_id": WHISPER_MODELS[name],
            "size_mb": MODEL_SIZES_MB.get(name, 0),
            "cached": is_model_cached(name),
        }
    return models


if __name__ == "__main__":
    # CLI usage for testing
    import argparse
    parser = argparse.ArgumentParser(description="Download Whisper models")
    parser.add_argument("model", nargs="?", default="base", help="Model to download")
    parser.add_argument("--list", action="store_true", help="List available models")
    parser.add_argument("--force", action="store_true", help="Force re-download")
    args = parser.parse_args()

    if args.list:
        models = list_available_models()
        for name, info in models.items():
            status = "✓ cached" if info["cached"] else "not downloaded"
            print(f"  {name}: {info['size_mb']}MB [{status}]")
    else:
        success = download_with_json_output(args.model, force=args.force)
        sys.exit(0 if success else 1)
