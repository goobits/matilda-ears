from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

ProgressCallback = Callable[[dict], None]

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

WHISPER_SIZES_MB = {
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

PARAKEET_MODELS = {"tdt-0.6b-v3": "mlx-community/parakeet-tdt-0.6b-v3"}


def get_huggingface_cache_dir() -> Path:
    try:
        from huggingface_hub import constants

        return Path(constants.HF_HUB_CACHE)
    except ImportError:
        return Path.home() / ".cache" / "huggingface" / "hub"


def _repo_is_cached(repo_id: str) -> bool:
    snapshots = get_huggingface_cache_dir() / f"models--{repo_id.replace('/', '--')}" / "snapshots"
    return snapshots.is_dir() and any(snapshot.is_dir() and any(snapshot.iterdir()) for snapshot in snapshots.iterdir())


def is_model_cached(model_name: str, backend: str = "faster_whisper") -> bool:
    if backend == "parakeet":
        return _repo_is_cached(PARAKEET_MODELS.get(model_name, model_name))
    if backend == "huggingface":
        return _repo_is_cached(model_name)
    repo_id = WHISPER_MODELS.get(model_name)
    return bool(repo_id and _repo_is_cached(repo_id))


def _emit(callback: ProgressCallback | None, **data: Any) -> None:
    if callback:
        callback(data)


def download_model(
    model_name: str | None = None,
    *,
    backend: str = "faster_whisper",
    progress_callback: ProgressCallback | None = None,
    force: bool = False,
) -> bool:
    defaults = {"faster_whisper": "base", "parakeet": "tdt-0.6b-v3"}
    model_name = model_name or defaults.get(backend)
    if not model_name:
        _emit(progress_callback, status="error", error=f"--model is required for backend {backend}")
        return False
    if backend == "parakeet":
        repo_id = PARAKEET_MODELS.get(model_name, model_name)
    elif backend == "huggingface":
        repo_id = model_name
    else:
        whisper_repo_id = WHISPER_MODELS.get(model_name)
        if whisper_repo_id is None:
            _emit(
                progress_callback,
                status="error",
                error=f"Unknown faster-whisper model: {model_name}. Available: {', '.join(WHISPER_MODELS)}",
            )
            return False
        repo_id = whisper_repo_id
    try:
        from huggingface_hub import snapshot_download

        _emit(progress_callback, status="downloading", model=model_name, progress=0.0, repo_id=repo_id)
        snapshot_download(repo_id=repo_id, repo_type="model", local_files_only=False, force_download=force)
        _emit(progress_callback, status="complete", model=model_name, progress=1.0)
        return True
    except Exception as exc:
        _emit(progress_callback, status="error", model=model_name, error=str(exc))
        return False


def download_with_json_output(
    model_name: str | None = None, *, backend: str = "faster_whisper", force: bool = False
) -> bool:
    def json_callback(data: dict) -> None:
        print(json.dumps(data), flush=True)

    return download_model(model_name, backend=backend, progress_callback=json_callback, force=force)


def list_available_models(backend: str | None = None) -> dict:
    catalogs = {
        "faster_whisper": {
            name: {
                "repo_id": repo_id,
                "size_mb": WHISPER_SIZES_MB.get(name, 0),
                "cached": is_model_cached(name, backend="faster_whisper"),
            }
            for name, repo_id in WHISPER_MODELS.items()
        },
        "parakeet": {
            name: {"repo_id": repo_id, "cached": is_model_cached(name, backend="parakeet")}
            for name, repo_id in PARAKEET_MODELS.items()
        },
        "huggingface": {},
    }
    if backend:
        if backend not in catalogs:
            raise ValueError(f"Backend has no downloadable model catalog: {backend}")
        return catalogs[backend]
    return catalogs
