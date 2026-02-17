from __future__ import annotations

import ast
from pathlib import Path

import matilda_ears.transcription.streaming as streaming_pkg


def _iter_streaming_source_files() -> list[Path]:
    root = Path(streaming_pkg.__file__).resolve().parent
    files: list[Path] = []
    for path in root.rglob("*.py"):
        # Ignore vendored code entirely (it is allowed to import whatever it needs).
        if "vendor" in path.parts:
            continue
        if "__pycache__" in path.parts:
            continue
        files.append(path)
    return sorted(files)


def _imports_vendor(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "matilda_ears.transcription.streaming.vendor" in alias.name:
                    return True
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            # Relative import from `.vendor` or `from .vendor.x import y`.
            if node.level == 1 and (module == "vendor" or module.startswith("vendor.")):
                return True
            # Absolute import.
            if module.startswith("matilda_ears.transcription.streaming.vendor"):
                return True
    return False


def test_only_adapter_imports_vendor():
    allowed = {"adapter.py"}
    violations: list[Path] = []
    for path in _iter_streaming_source_files():
        if path.name in allowed:
            continue
        if _imports_vendor(path):
            violations.append(path)

    assert violations == [], f"Vendor imports outside adapter: {violations}"
