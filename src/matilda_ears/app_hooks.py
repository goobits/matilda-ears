"""Hook implementations for Matilda Ears - Speech-to-Text Engine.

This file contains the business logic for your CLI commands.
Implement the hook functions below to handle your CLI commands.

IMPORTANT: Hook names must use snake_case with 'on_' prefix
Example:
- Command 'hello' -> Hook function 'on_hello'
- Command 'hello-world' -> Hook function 'on_hello_world'
"""

# Import any modules you need here
import json as json_module
from typing import Any, Dict, Optional


def on_status(json: bool = False, **kwargs) -> Dict[str, Any]:
    """Handle status command - show system status and capabilities.

    Args:
        json: Output JSON format

    Returns:
        Dictionary with status and optional results
    """
    from .core.config import get_config
    from .utils.model_downloader import is_model_cached

    config = get_config()

    status = {
        "backend": config.transcription_backend,
        "model": config.whisper_model,
        "device": config.whisper_device_auto,
        "compute_type": config.whisper_compute_type_auto,
        "model_cached": is_model_cached(config.whisper_model),
        "websocket_port": config.websocket_port,
    }

    if json:
        print(json_module.dumps(status, indent=2))
    else:
        print("Matilda Ears Status")
        print("=" * 40)
        print(f"  Backend:      {status['backend']}")
        print(f"  Model:        {status['model']}")
        print(f"  Device:       {status['device']}")
        print(f"  Compute Type: {status['compute_type']}")
        print(f"  Model Cached: {'Yes' if status['model_cached'] else 'No'}")
        print(f"  WebSocket:    port {status['websocket_port']}")

    return {"status": "success", "data": status}


def on_models(json: bool = False, **kwargs) -> Dict[str, Any]:
    """Handle models command - list available Whisper models.

    Args:
        json: Output JSON format

    Returns:
        Dictionary with status and optional results
    """
    from .utils.model_downloader import list_available_models

    models = list_available_models()

    if json:
        print(json_module.dumps(models, indent=2))
    else:
        print("Available Whisper Models")
        print("=" * 50)
        for name, info in sorted(models.items()):
            status = "✓ cached" if info["cached"] else "not downloaded"
            size = f"{info['size_mb']}MB"
            print(f"  {name:20} {size:>8}  [{status}]")
        print()
        print("Use 'ears download <model>' to download a model")

    return {"status": "success", "data": models}


def on_download(model: Optional[str] = None, progress: bool = False, **kwargs) -> Dict[str, Any]:
    """Handle download command - download Whisper model for offline use.

    Args:
        model: Model size to download (tiny, base, small, medium, large-v3-turbo)
        progress: Show JSON progress events (for programmatic use)

    Returns:
        Dictionary with status and optional results
    """
    from .utils.model_downloader import download_model, download_with_json_output, is_model_cached

    # Default model
    if model is None:
        model = "base"

    if progress:
        # JSON output mode for Tauri integration
        success = download_with_json_output(model)
        return {"status": "success" if success else "error"}
    else:
        # Human-readable output
        if is_model_cached(model):
            print(f"Model '{model}' is already downloaded.")
            return {"status": "success", "cached": True}

        print(f"Downloading model: {model}")
        print("This may take a few minutes depending on your connection...")
        print()

        def progress_callback(data: dict):
            status = data.get("status", "")
            if status == "downloading":
                pct = int(data.get("progress", 0) * 100)
                downloaded = data.get("downloaded_mb", 0)
                total = data.get("total_mb", 0)
                print(f"\r  Progress: {pct}% ({downloaded}/{total} MB)", end="", flush=True)
            elif status == "complete":
                print(f"\n\n✓ Model '{model}' downloaded successfully!")
            elif status == "error":
                print(f"\n\n✗ Error: {data.get('error', 'Unknown error')}")

        success = download_model(model, progress_callback=progress_callback)
        return {"status": "success" if success else "error"}


def on_train_wake_word(
    phrase: Optional[str] = None,
    output: Optional[str] = None,
    samples: Optional[str] = "3000",
    epochs: Optional[str] = "10",
    **kwargs
) -> Dict[str, Any]:
    """Train a custom wake word model using Modal.com cloud GPU.

    Args:
        phrase: The wake word phrase to train (e.g., 'hey matilda')
        output: Output path for ONNX file (default: models/{phrase}.onnx)
        samples: Number of training samples to generate
        epochs: Number of training epochs

    Returns:
        Dictionary with status and optional results
    """
    from .wake_word.application.train_wake_word import train_wake_word

    return train_wake_word(phrase=phrase, output=output, samples=samples, epochs=epochs)
