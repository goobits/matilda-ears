#!/usr/bin/env python3
"""Install or refresh the isolated Matilda Ears test environment."""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = ROOT / ".artifacts/test/test-env"


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"-h", "--help"}:
        print("Usage: ./scripts/test.py --install")
        return 0

    scripts = "Scripts" if os.name == "nt" else "bin"
    executable = "python.exe" if os.name == "nt" else "python"
    python = ENVIRONMENT / scripts / executable
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(ENVIRONMENT)

    environment = {**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    transport = ROOT.parent / "matilda-transport"
    if transport.is_dir():
        subprocess.run([str(python), "-m", "pip", "install", "-e", str(transport)], env=environment, check=True)
    subprocess.run([str(python), "-m", "pip", "install", "-e", f"{ROOT}[dev]"], env=environment, check=True)
    return subprocess.run([str(python), str(ROOT / "tests/__tools__/verify_test_setup.py")], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
