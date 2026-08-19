from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
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
MOSS_REPO_ID = "mudler/moss-transcribe.cpp-gguf"
MOSS_MODEL_REVISION = "54e4bbd17da3f84adf1c1bcf7791b9b9266f741e"
MOSS_RUNTIME_REPO = "https://github.com/localai-org/moss-transcribe.cpp.git"
MOSS_RUNTIME_REVISION = "190a569c13b4b247450f2fb3b2a431244e84833e"
MOSS_MODELS = {
    "q8_0": "moss-transcribe-q8_0.gguf",
    "q5_k": "moss-transcribe-q5_k.gguf",
}
MOSS_SIZES_MB = {"q8_0": 942, "q5_k": 619}


def get_moss_cache_dir() -> Path:
    configured = os.environ.get("EARS_MOSS_CACHE")
    return Path(configured).expanduser() if configured else Path.home() / ".cache" / "matilda-ears" / "moss"


def get_moss_runtime_path() -> Path:
    executable = "moss-transcribe.exe" if platform.system() == "Windows" else "moss-transcribe"
    build_dir = get_moss_cache_dir() / f"source-{MOSS_RUNTIME_REVISION[:12]}" / "build"
    release_path = build_dir / "Release" / executable
    return release_path if release_path.exists() else build_dir / executable


def is_moss_runtime_installed(configured_binary: str | None = None) -> bool:
    binary = os.environ.get("EARS_MOSS_BINARY") or configured_binary
    if not binary or binary == "auto":
        binary = str(get_moss_runtime_path())
    expanded = Path(binary).expanduser()
    if expanded.parent != Path() or expanded.is_absolute():
        return expanded.is_file() and os.access(expanded, os.X_OK)
    return shutil.which(binary) is not None


def get_moss_model_path(model_name: str = "q8_0") -> Path | None:
    path = Path(model_name).expanduser()
    if path.is_file():
        return path
    filename = MOSS_MODELS.get(model_name)
    if filename is None:
        return None
    try:
        from huggingface_hub import try_to_load_from_cache

        cached = try_to_load_from_cache(MOSS_REPO_ID, filename, revision=MOSS_MODEL_REVISION)
        return Path(cached) if isinstance(cached, str) and Path(cached).is_file() else None
    except ImportError:
        return None


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
    if backend == "moss":
        return get_moss_model_path(model_name) is not None
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
    defaults = {"faster_whisper": "base", "parakeet": "tdt-0.6b-v3", "moss": "q8_0"}
    model_name = model_name or defaults.get(backend)
    if not model_name:
        _emit(progress_callback, status="error", error=f"--model is required for backend {backend}")
        return False
    if backend == "moss":
        filename = MOSS_MODELS.get(model_name)
        if filename is None:
            _emit(
                progress_callback,
                status="error",
                error=f"Unknown MOSS model: {model_name}. Available: {', '.join(MOSS_MODELS)}",
            )
            return False
        try:
            _install_moss_runtime(progress_callback)
            from huggingface_hub import hf_hub_download

            _emit(progress_callback, status="downloading", model=model_name, progress=0.0, repo_id=MOSS_REPO_ID)
            hf_hub_download(
                repo_id=MOSS_REPO_ID,
                filename=filename,
                revision=MOSS_MODEL_REVISION,
                force_download=force,
            )
            _emit(progress_callback, status="complete", model=model_name, progress=1.0)
            return True
        except Exception as exc:
            _emit(progress_callback, status="error", model=model_name, error=str(exc))
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
        "moss": {
            name: {
                "repo_id": MOSS_REPO_ID,
                "filename": filename,
                "size_mb": MOSS_SIZES_MB[name],
                "cached": is_model_cached(name, backend="moss"),
            }
            for name, filename in MOSS_MODELS.items()
        },
        "huggingface": {},
    }
    if backend:
        if backend not in catalogs:
            raise ValueError(f"Backend has no downloadable model catalog: {backend}")
        return catalogs[backend]
    return catalogs


def _install_moss_runtime(progress_callback: ProgressCallback | None = None) -> Path:
    runtime = get_moss_runtime_path()
    if is_moss_runtime_installed(str(runtime)):
        return runtime

    for command in ("git", "cmake"):
        if shutil.which(command) is None:
            raise RuntimeError(f"{command} is required to install the MOSS native runtime")

    source_dir = get_moss_cache_dir() / f"source-{MOSS_RUNTIME_REVISION[:12]}"
    build_dir = source_dir / "build"
    source_dir.parent.mkdir(parents=True, exist_ok=True)
    _emit(progress_callback, status="building", runtime="moss", revision=MOSS_RUNTIME_REVISION)

    if not (source_dir / ".git").is_dir():
        subprocess.run(
            ["git", "clone", "--recursive", MOSS_RUNTIME_REPO, str(source_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
    subprocess.run(
        ["git", "-C", str(source_dir), "checkout", "--detach", MOSS_RUNTIME_REVISION],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(source_dir), "submodule", "update", "--init", "--recursive"],
        check=True,
        capture_output=True,
        text=True,
    )
    configure = ["cmake", "-S", str(source_dir), "-B", str(build_dir), "-DCMAKE_BUILD_TYPE=Release"]
    if platform.system() == "Darwin":
        configure.append("-DMT_GGML_METAL=ON")
    subprocess.run(configure, check=True, capture_output=True, text=True)
    subprocess.run(
        ["cmake", "--build", str(build_dir), "--config", "Release", "-j"],
        check=True,
        capture_output=True,
        text=True,
    )
    runtime = get_moss_runtime_path()
    if not is_moss_runtime_installed(str(runtime)):
        raise RuntimeError(f"MOSS build completed without creating {runtime}")
    return runtime
