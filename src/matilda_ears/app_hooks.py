"""Hook implementations for Matilda Ears - Speech-to-Text Engine.

This file contains the business logic for your CLI commands.
Implement the hook functions below to handle your CLI commands.

IMPORTANT: Hook names must use snake_case with 'on_' prefix
Example:
- Command 'hello' -> Hook function 'on_hello'
- Command 'hello-world' -> Hook function 'on_hello_world'
"""

import asyncio
import json as json_module
import os
from typing import Any


def _prepare_runtime(ctx=None, model: str | None = None, inference_device: str | None = None) -> None:
    config_file = getattr(getattr(ctx, "config", None), "config_file", None)
    if config_file is not None:
        os.environ["MATILDA_CONFIG"] = str(config_file)
    if model:
        os.environ["EARS_MODEL"] = model
    if inference_device:
        os.environ["EARS_DEVICE"] = inference_device


def _mode_config(config_class, ctx, model, language, device, sample_rate, json, debug, **extra):
    _prepare_runtime(ctx, model=model)
    return config_class(
        debug=bool(debug or getattr(ctx, "debug", False)),
        format="json" if json else "text",
        sample_rate=sample_rate,
        device=device,
        language=language,
        model=model,
        **extra,
    )


def on_listen_once(
    model: str | None = None,
    language: str | None = None,
    device: str | None = None,
    sample_rate: int = 16000,
    json: bool = False,
    debug: bool = False,
    ctx=None,
    **kwargs,
) -> None:
    from .core.mode_config import ListenOnceConfig
    from .modes.listen_once import ListenOnceMode

    config = _mode_config(ListenOnceConfig, ctx, model, language, device, sample_rate, json, debug)
    asyncio.run(ListenOnceMode(config).run())


def on_conversation(
    model: str | None = None,
    language: str | None = None,
    device: str | None = None,
    sample_rate: int = 16000,
    json: bool = False,
    debug: bool = False,
    ctx=None,
    **kwargs,
) -> None:
    from .core.mode_config import ConversationConfig
    from .modes.conversation import ConversationMode

    config = _mode_config(ConversationConfig, ctx, model, language, device, sample_rate, json, debug)
    asyncio.run(ConversationMode(config).run())


def on_wake_word(
    agent_aliases: str | None = None,
    threshold: float | None = None,
    backend: str | None = None,
    access_key: str | None = None,
    model: str | None = None,
    language: str | None = None,
    device: str | None = None,
    sample_rate: int = 16000,
    json: bool = False,
    debug: bool = False,
    ctx=None,
    **kwargs,
) -> None:
    from .core.mode_config import WakeWordConfig
    from .wake_word.mode import WakeWordMode

    config = _mode_config(
        WakeWordConfig,
        ctx,
        model,
        language,
        device,
        sample_rate,
        json,
        debug,
        agent_aliases=agent_aliases,
        threshold=threshold,
        backend=backend,
        access_key=access_key,
    )
    asyncio.run(WakeWordMode(config).run())


def on_transcribe(
    file: str | None,
    model: str | None = None,
    language: str | None = None,
    backend: str | None = None,
    diarize: bool = False,
    no_formatting: bool = False,
    json: bool = False,
    debug: bool = False,
    ctx=None,
    **kwargs,
) -> None:
    if not file:
        raise SystemExit("Audio file path is required")

    from .core.mode_config import FileTranscribeConfig
    from .modes.file_transcribe import FileTranscribeMode

    config = _mode_config(
        FileTranscribeConfig,
        ctx,
        model,
        language,
        None,
        None,
        json,
        debug,
        file=file,
        no_formatting=no_formatting,
        backend=backend,
        diarize=diarize,
    )
    asyncio.run(FileTranscribeMode(config).run())


def on_serve(
    host: str | None = None,
    port: int | None = None,
    model: str | None = None,
    device: str | None = None,
    ctx=None,
    **kwargs,
) -> None:
    _prepare_runtime(ctx, model=model, inference_device=device)

    from .transcription.server.core import MatildaWebSocketServer

    server = MatildaWebSocketServer()
    asyncio.run(server.start_server(host, port))


def _configured_model(config, backend: str) -> str | None:
    if backend == "faster_whisper":
        return config.whisper_model
    if backend == "moss" and os.environ.get("EARS_MOSS_MODEL"):
        return os.environ["EARS_MOSS_MODEL"]
    key = {"parakeet": "parakeet.model", "huggingface": "huggingface.model", "moss": "moss.model"}.get(backend)
    return str(config.get(key)) if key and config.get(key) else None


def on_status(json: bool = False, ctx=None, **kwargs) -> dict[str, Any]:
    """Handle status command - show system status and capabilities.

    Args:
        json: Output JSON format

    Returns:
        Dictionary with status and optional results

    """
    _prepare_runtime(ctx)

    from .core.config import get_config
    from .transcription.backends import normalize_backend_name
    from .transcription.model_store import is_model_cached

    config = get_config()

    backend = normalize_backend_name(config.transcription_backend)
    model = _configured_model(config, backend)
    status = {
        "backend": backend,
        "model": model,
    }
    if backend == "faster_whisper":
        status["device"] = config.whisper_device_auto
        status["compute_type"] = config.whisper_compute_type_auto
    status["model_cached"] = bool(model and is_model_cached(model, backend=backend))
    if backend == "moss":
        from .transcription.model_store import is_moss_runtime_installed

        status["runtime_installed"] = is_moss_runtime_installed(config.get("moss.binary"))
    status["websocket_port"] = config.websocket_port

    if json:
        print(json_module.dumps(status, indent=2))
    else:
        print("Matilda Ears Status")
        print("=" * 40)
        print(f"  Backend:      {status['backend']}")
        print(f"  Model:        {status['model']}")
        if "device" in status:
            print(f"  Device:       {status['device']}")
            print(f"  Compute Type: {status['compute_type']}")
        print(f"  Model Cached: {'Yes' if status['model_cached'] else 'No'}")
        if "runtime_installed" in status:
            print(f"  Runtime:      {'Installed' if status['runtime_installed'] else 'Missing'}")
        print(f"  WebSocket:    port {status['websocket_port']}")

    return {"status": "success", "data": status}


def on_models(backend: str | None = None, json: bool = False, ctx=None, **kwargs) -> dict[str, Any]:
    """Handle models command - list available transcription models.

    Args:
        json: Output JSON format

    Returns:
        Dictionary with status and optional results

    """
    _prepare_runtime(ctx)

    from .transcription.backends import normalize_backend_name
    from .transcription.model_store import list_available_models

    selected_backend = normalize_backend_name(backend) if backend else None
    if selected_backend == "auto":
        selected_backend = None
    models = list_available_models(selected_backend)

    if json:
        print(json_module.dumps(models, indent=2))
    else:
        print("Available Transcription Models")
        print("=" * 50)
        catalogs = {selected_backend: models} if selected_backend else models
        for catalog_backend, catalog in catalogs.items():
            print(f"  {catalog_backend}")
            for name, info in sorted(catalog.items()):
                status = "✓ cached" if info["cached"] else "not downloaded"
                size = f"{info.get('size_mb', '?')}MB"
                print(f"    {name:20} {size:>8}  [{status}]")
        print()
        print("Use 'ears download --backend <backend> --model <model>' to download a model")

    return {"status": "success", "data": models}


def on_download(
    model: str | None = None,
    backend: str = "faster_whisper",
    progress: bool = False,
    ctx=None,
    **kwargs,
) -> dict[str, Any]:
    """Handle download command - download a transcription model for offline use.

    Args:
        model: Model size to download (tiny, base, small, medium, large-v3-turbo)
        progress: Show JSON progress events (for programmatic use)

    Returns:
        Dictionary with status and optional results

    """
    _prepare_runtime(ctx)

    from .transcription.backends import normalize_backend_name
    from .transcription.model_store import download_model, download_with_json_output, is_model_cached

    backend = normalize_backend_name(backend)
    defaults = {"faster_whisper": "base", "parakeet": "tdt-0.6b-v3", "moss": "q8_0"}
    model = model or defaults.get(backend)

    if progress:
        success = download_with_json_output(model, backend=backend)
        return {"status": "success" if success else "error"}
    else:
        model_ready = bool(model and is_model_cached(model, backend=backend))
        if backend == "moss":
            from .transcription.model_store import is_moss_runtime_installed

            model_ready = model_ready and is_moss_runtime_installed()
        if model_ready:
            print(f"Model '{model}' is already downloaded.")
            return {"status": "success", "cached": True}

        print(f"Preparing {backend} model: {model}")
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

        success = download_model(model, backend=backend, progress_callback=progress_callback)
        return {"status": "success" if success else "error"}


def on_train_wake_word(
    phrase: str | None = None,
    output: str | None = None,
    samples: str | None = "3000",
    epochs: str | None = "10",
    ctx=None,
    **kwargs,
) -> dict[str, Any]:
    """Train a custom wake word model using Modal.com cloud GPU.

    Args:
        phrase: The wake word phrase to train (e.g., 'hey matilda')
        output: Output path for ONNX file (default: internal/models/{phrase}.onnx)
        samples: Number of training samples to generate
        epochs: Number of training epochs

    Returns:
        Dictionary with status and optional results

    """
    _prepare_runtime(ctx)

    from .wake_word.internal.training import train_wake_word

    return train_wake_word(phrase=phrase, output=output, samples=samples, epochs=epochs)
