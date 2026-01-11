from pathlib import Path


def get_models_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "internal" / "models"


def ensure_output_path(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path
