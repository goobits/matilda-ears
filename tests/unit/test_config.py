from matilda_ears.core import token_store
from matilda_ears.core.config import DEFAULT_WEBSOCKET_HEALTH_PORT, DEFAULT_WEBSOCKET_PORT, ConfigLoader


def test_default_jwt_secret_is_persistent(monkeypatch, tmp_path):
    data_dir = tmp_path / "ears"
    monkeypatch.delenv("STT_JWT_SECRET", raising=False)
    monkeypatch.setattr(token_store, "get_default_data_dir", lambda: data_dir)

    first = ConfigLoader(tmp_path / "missing.toml").jwt_secret_key
    second = ConfigLoader(tmp_path / "missing.toml").jwt_secret_key

    assert first == second
    assert len(first) >= 32
    assert (data_dir / "jwt_secret.key").read_text(encoding="utf-8") == first


def test_environment_jwt_secret_has_priority(monkeypatch, tmp_path):
    secret = "environment-secret-with-enough-unique-characters-123"
    monkeypatch.setenv("STT_JWT_SECRET", secret)

    assert ConfigLoader(tmp_path / "missing.toml").jwt_secret_key == secret


def test_port_defaults_and_environment_ownership(monkeypatch, tmp_path):
    for name in ("MATILDA_PORT_EARS_WS", "MATILDA_PORT_EARS_HEALTH", "EARS_PORT", "EARS_HEALTH_PORT"):
        monkeypatch.delenv(name, raising=False)
    config = ConfigLoader(tmp_path / "missing.toml")

    assert config.websocket_port == DEFAULT_WEBSOCKET_PORT
    assert config.websocket_health_port == DEFAULT_WEBSOCKET_HEALTH_PORT

    monkeypatch.setenv("MATILDA_PORT_EARS_WS", "4100")
    monkeypatch.setenv("MATILDA_PORT_EARS_HEALTH", "4200")
    assert config.websocket_port == 4100
    assert config.websocket_health_port == 4200


def test_custom_cli_port_gets_adjacent_health_port(monkeypatch, tmp_path):
    monkeypatch.delenv("MATILDA_PORT_EARS_HEALTH", raising=False)
    monkeypatch.delenv("EARS_HEALTH_PORT", raising=False)
    config = ConfigLoader(tmp_path / "missing.toml")

    assert config.websocket_health_port_for(9000) == 9001


def test_config_instances_do_not_mutate_shared_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("MATILDA_LOCALE", "fr-FR")
    localized = ConfigLoader(tmp_path / "first-missing.toml")
    monkeypatch.delenv("MATILDA_LOCALE")
    defaulted = ConfigLoader(tmp_path / "second-missing.toml")

    assert localized.get("ears_tuner.locale") == "fr-FR"
    assert defaulted.get("ears_tuner.locale") == "en-US"


def test_backend_alias_is_normalized_at_config_boundary(monkeypatch, tmp_path):
    monkeypatch.setenv("EARS_BACKEND", "whisper")

    assert ConfigLoader(tmp_path / "missing.toml").transcription_backend == "faster_whisper"
