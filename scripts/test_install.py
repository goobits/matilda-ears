#!/usr/bin/env python3
"""Test environment install/bootstrap helper for Ears."""

from __future__ import annotations

import os
import platform
import subprocess
import sys


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"-h", "--help"}:
        print("Usage: ./scripts/test.py --install")
        print("Installs Ears test/dev dependencies in the isolated test environment.")
        return 0

    print("🔧 GOOBITS STT Installation")
    print("=" * 50)

    in_venv = sys.prefix != sys.base_prefix or os.environ.get("VIRTUAL_ENV") is not None
    python_exe = sys.executable

    if not in_venv:
        print("⚠️  Not in a virtual environment!")
        os.makedirs(".artifacts/test", exist_ok=True)
        test_env_path = os.path.join(".artifacts/test", "test-env")

        if not os.path.exists(test_env_path):
            print("\nCreating test environment...")
            try:
                subprocess.run([sys.executable, "-m", "venv", test_env_path], check=True)
                print(f"✅ Test environment created in {test_env_path}")
            except subprocess.CalledProcessError as exc:
                print(f"❌ Failed to create test environment: {exc}")
                print("   Try running: python3 -m venv .artifacts/test/test-env")
                return 1
        else:
            print(f"✅ Using existing test environment in {test_env_path}")

        if platform.system() == "Windows":
            python_exe = os.path.join(test_env_path, "Scripts", "python.exe")
            print(f"\n📝 Activate it with:\n   .\\{test_env_path}\\Scripts\\activate")
        else:
            python_exe = os.path.join(test_env_path, "bin", "python")
            print(f"\n📝 Activate it with:\n   source {test_env_path}/bin/activate")
        print("\nUsing test environment's pip for installation...")
    else:
        print("✅ Already in a virtual environment")

    if not os.path.exists(python_exe):
        print(f"❌ Python executable not found at {python_exe}")
        return 1

    print("\n📦 Installing GOOBITS STT with all dependencies...")
    result = subprocess.run([python_exe, "-m", "pip", "install", "-e", ".[dev]"], check=False)
    if result.returncode != 0:
        print("\n❌ Installation failed!")
        print("   Check the error messages above for details.")
        return 1

    print("\n✅ Installation complete!")
    print("\n📥 Installing SpaCy English language model...")
    spacy_cmd = [python_exe, "-m", "spacy", "download", "en_core_web_sm"]
    spacy_result = subprocess.run(spacy_cmd, check=False)
    if spacy_result.returncode == 0:
        print("✅ SpaCy model installed successfully!")
    else:
        print("⚠️  SpaCy model installation failed, trying fallback method...")
        fallback_cmd = [
            python_exe,
            "-m",
            "pip",
            "install",
            "en_core_web_sm@https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl",
        ]
        fallback_result = subprocess.run(fallback_cmd, check=False)
        if fallback_result.returncode == 0:
            print("✅ SpaCy model installed via fallback method!")
        else:
            print("❌ SpaCy model installation failed!")
            print("   Ears Tuner may not work properly.")

    print("\n🧪 Verifying installation...")
    verify_cmd = [python_exe, "tests/__tools__/verify_test_setup.py"]
    subprocess.run(verify_cmd, check=False)
    print("\n🚀 Ready to run tests with: ./test.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
