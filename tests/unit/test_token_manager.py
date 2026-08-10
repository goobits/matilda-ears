import json
import stat
from unittest.mock import patch

import pytest

from matilda_ears.core.token_manager import TokenManager
from matilda_ears.core.token_store import TokenStoreError

TEST_SECRET_KEY = "test_secret_key_for_unit_tests____32_bytes_minimum____"


@pytest.fixture
def temp_data_dir(tmp_path):
    return tmp_path / "ears"


@pytest.fixture
def token_manager(temp_data_dir):
    return TokenManager(secret_key=TEST_SECRET_KEY, data_dir=temp_data_dir)


def test_token_generation_and_validation(token_manager):
    token_info = token_manager.generate_token("test_client")

    payload = token_manager.validate_token(token_info["token"])

    assert token_info["client_name"] == "test_client"
    assert payload is not None
    assert payload["client_name"] == "test_client"


def test_generated_secret_and_token_survive_restart(temp_data_dir):
    first = TokenManager(data_dir=temp_data_dir)
    token_info = first.generate_token("persistent_client")

    second = TokenManager(data_dir=temp_data_dir)

    assert second.secret_key == first.secret_key
    assert second.validate_token(token_info["token"]) is not None


def test_revocation_is_durable_before_return(token_manager, temp_data_dir):
    token_info = token_manager.generate_token("revoked_client")

    assert token_manager.revoke_token(token_info["token_id"])

    restarted = TokenManager(secret_key=TEST_SECRET_KEY, data_dir=temp_data_dir)
    assert restarted.validate_token(token_info["token"]) is None


def test_throttled_activity_save_is_ordered(token_manager):
    token = token_manager.generate_token("throttled_client")["token"]

    with patch.object(token_manager, "_save_tokens", wraps=token_manager._save_tokens) as save:
        token_manager.validate_token(token)
        save.assert_not_called()

        token_manager._last_save_time = 0.0
        token_manager.validate_token(token)
        save.assert_called_once()

        save.reset_mock()
        token_manager.validate_token(token)
        save.assert_not_called()


def test_one_time_token_is_consumed_by_default(token_manager):
    token = token_manager.generate_token("onetime", one_time_use=True)["token"]

    assert token_manager.validate_token(token) is not None
    assert token_manager.validate_token(token) is None


def test_one_time_consumption_survives_restart(temp_data_dir):
    first = TokenManager(data_dir=temp_data_dir)
    token = first.generate_token("onetime", one_time_use=True)["token"]
    assert first.validate_token(token) is not None

    second = TokenManager(data_dir=temp_data_dir)

    assert second.validate_token(token) is None


def test_corrupt_state_fails_closed(temp_data_dir):
    first = TokenManager(secret_key=TEST_SECRET_KEY, data_dir=temp_data_dir)
    token = first.generate_token("corrupt")["token"]
    first.tokens_file.write_text("not-json", encoding="utf-8")

    restarted = TokenManager(secret_key=TEST_SECRET_KEY, data_dir=temp_data_dir)

    assert restarted.active_tokens == {}
    assert restarted.validate_token(token) is None


def test_failed_generation_is_not_left_active(token_manager):
    with patch.object(token_manager.store, "save_tokens", side_effect=TokenStoreError("disk unavailable")):
        with pytest.raises(ValueError, match="Token generation failed"):
            token_manager.generate_token("unsaved")

    assert token_manager.active_tokens == {}


def test_state_files_are_atomic_json_and_private(token_manager):
    for index in range(3):
        token_manager.generate_token(f"client-{index}")

    state = json.loads(token_manager.tokens_file.read_text(encoding="utf-8"))

    assert len(state) == 3
    assert stat.S_IMODE(token_manager.tokens_file.stat().st_mode) == 0o600
    assert not list(token_manager.data_dir.glob(".tokens.json.*"))
