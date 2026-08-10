from matilda_ears.core import token_store
from matilda_ears.core.config import ConfigLoader


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
