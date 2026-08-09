"""Docker dashboard integration for the canonical Matilda Ears runtime."""

from pathlib import Path
import tomllib


def _get_version() -> str:
    try:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return str(data["project"]["version"])
    except Exception:
        return "unknown"


__version__ = _get_version()
