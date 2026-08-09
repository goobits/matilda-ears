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
            ["recording.wav", "--no-formatting"],
            "on_transcribe",
            {"file": "recording.wav", "no_formatting": True},
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
