import ssl
from types import SimpleNamespace

from matilda_ears.utils import ssl as ssl_utils


def _config(verify_mode: str):
    return SimpleNamespace(
        ssl_verify_mode=verify_mode,
        ssl_cert_file="unused.crt",
        ssl_key_file="unused.key",
        ssl_auto_generate_certs=False,
        websocket_bind_host="127.0.0.1",
    )


def test_client_ssl_requires_certificate_verification(monkeypatch):
    monkeypatch.setattr(ssl_utils, "config", _config("required"))

    context = ssl_utils.create_ssl_context(mode="client", auto_generate=False)

    assert context is not None
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_client_ssl_allows_explicit_development_opt_out(monkeypatch):
    monkeypatch.setattr(ssl_utils, "config", _config("none"))

    context = ssl_utils.create_ssl_context(mode="client", auto_generate=False)

    assert context is not None
    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_NONE
