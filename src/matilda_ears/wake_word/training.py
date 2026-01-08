import subprocess
import sys
from pathlib import Path
from typing import Any

from .internal.model import WakeWordTrainingRequest, WakeWordTrainingResult
from .internal.trainer import normalize_model_name, validate_phrase
from .internal.storage import ensure_output_path, get_models_dir


def _parse_int(value: object | None, default: int, label: str) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise ValueError(f"{label} must be an integer")


def train_wake_word(
    phrase: str | None,
    output: str | None,
    samples: object | None,
    epochs: object | None,
) -> dict[str, Any]:
    try:
        phrase_value = validate_phrase(phrase)
    except ValueError:
        print("ERROR: Please provide a phrase to train.")
        print('Usage: ears train-wake-word "hey matilda"')
        return {"status": "error", "error": "No phrase provided"}

    model_name = normalize_model_name(phrase_value)

    if output is None:
        output_path = get_models_dir() / f"{model_name}.onnx"
    else:
        output_path = Path(output)

    ensure_output_path(output_path)

    try:
        samples_value = _parse_int(samples, 3000, "samples")
        epochs_value = _parse_int(epochs, 10, "epochs")
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return {"status": "error", "error": str(exc)}

    request = WakeWordTrainingRequest(
        phrase=phrase_value,
        output_path=output_path,
        samples=samples_value,
        epochs=epochs_value,
    )

    print("=" * 60)
    print(f"Training wake word model: '{request.phrase}'")
    print("=" * 60)
    print()
    print("This uses Modal.com's cloud GPU (free tier: 30 GPU-hours/month)")
    print("Training typically takes 20-40 minutes.")
    print()

    try:
        import modal  # noqa: F401
    except ImportError:
        print("Modal is not installed. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "modal"], check=True)
        print()

    modal_toml = Path.home() / ".modal.toml"
    if not modal_toml.exists():
        print("ERROR: Modal is not authenticated.")
        print()
        print("To set up Modal:")
        print("  1. Sign up at https://modal.com (free)")
        print("  2. Run: modal token set --token-id <id> --token-secret <secret>")
        print("  3. Try this command again")
        print()
        return {"status": "error", "error": "Modal not authenticated"}

    print("Starting training on Modal cloud GPU...")
    print(f"Output will be saved to: {request.output_path}")
    print()

    modal_script = Path(__file__).resolve().parent / "internal" / "modal_train.py"

    result = subprocess.run(
        [
            "modal",
            "run",
            str(modal_script),
            "--phrase",
            request.phrase,
            "--output",
            str(request.output_path),
            "--samples",
            str(request.samples),
            "--epochs",
            str(request.epochs),
        ],
        check=False,
        capture_output=False,
    )

    if result.returncode == 0 and request.output_path.exists():
        print()
        print("=" * 60)
        print(f"✓ SUCCESS! Model saved to: {request.output_path}")
        print("=" * 60)
        print()
        print("To use your new wake word:")
        print(f'  ears --wake-word --agent-aliases="Matilda:{model_name}"')
        print()
        result_obj = WakeWordTrainingResult(status="success", model_path=request.output_path)
        return {"status": result_obj.status, "model_path": str(result_obj.model_path)}

    print()
    print("=" * 60)
    print("✗ Training failed. Check the logs above for errors.")
    print("=" * 60)
    result_obj = WakeWordTrainingResult(status="error", error="Training failed")
    return {"status": result_obj.status, "error": result_obj.error}
