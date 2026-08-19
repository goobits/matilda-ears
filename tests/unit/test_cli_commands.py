import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from matilda_ears import app_hooks
from matilda_ears.cli import cli


@pytest.mark.parametrize(
    ("command", "arguments", "hook_name", "expected"),
    [
        ("listen-once", ["--sample-rate", "8000", "--json"], "on_listen_once", {"sample_rate": 8000, "json": True}),
        ("conversation", ["--language", "es"], "on_conversation", {"language": "es"}),
        (
            "wake-word",
            ["--agent-aliases", "Matilda:computer", "--threshold", "0.25"],
            "on_wake_word",
            {"agent_aliases": "Matilda:computer", "threshold": 0.25},
        ),
        (
            "transcribe",
            ["recording.wav", "--backend", "huggingface", "--no-formatting"],
            "on_transcribe",
            {"file": "recording.wav", "backend": "huggingface", "no_formatting": True},
        ),
        ("serve", ["--host", "127.0.0.1", "--port", "3212"], "on_serve", {"host": "127.0.0.1", "port": 3212}),
    ],
)
def test_generated_runtime_commands_invoke_hooks(monkeypatch, command, arguments, hook_name, expected):
    hook = Mock()
    monkeypatch.setattr(app_hooks, hook_name, hook)

    result = CliRunner().invoke(cli, [command, *arguments])

    assert result.exit_code == 0, result.output
    hook.assert_called_once()
    for key, value in expected.items():
        assert hook.call_args.kwargs[key] == value


def test_transcribe_requires_file_path():
    result = CliRunner().invoke(cli, ["transcribe"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)


def test_status_json_output_contract(monkeypatch, capsys):
    config = SimpleNamespace(
        transcription_backend="faster-whisper",
        whisper_model="base",
        whisper_device_auto="cpu",
        whisper_compute_type_auto="int8",
        websocket_port=3211,
    )
    monkeypatch.setattr("matilda_ears.core.config.get_config", lambda: config)
    monkeypatch.setattr(
        "matilda_ears.transcription.model_store.is_model_cached", lambda _model, backend="faster_whisper": True
    )

    result = app_hooks.on_status(json=True)
    status = {
        "backend": "faster_whisper",
        "model": "base",
        "device": "cpu",
        "compute_type": "int8",
        "model_cached": True,
        "websocket_port": 3211,
    }

    assert capsys.readouterr().out == f"{json.dumps(status, indent=2)}\n"
    assert result == {"status": "success", "data": status}


def test_models_json_output_contract(monkeypatch, capsys):
    models = {"base": {"size_mb": 142, "cached": False}}
    monkeypatch.setattr("matilda_ears.transcription.model_store.list_available_models", lambda _backend=None: models)

    result = app_hooks.on_models(backend="faster_whisper", json=True)

    assert capsys.readouterr().out == f"{json.dumps(models, indent=2)}\n"
    assert result == {"status": "success", "data": models}
