import json
import shutil
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from matilda_ears.core.token_manager import TokenManager

@pytest.fixture
def temp_data_dir(tmp_path):
    data_dir = tmp_path / "ears"
    data_dir.mkdir()
    return data_dir

@pytest.fixture
def token_manager(temp_data_dir):
    return TokenManager(secret_key="test_secret", data_dir=temp_data_dir)

def test_token_generation_and_validation(token_manager):
    token_info = token_manager.generate_token("test_client")
    token = token_info["token"]

    assert token_info["client_name"] == "test_client"

    payload = token_manager.validate_token(token)
    assert payload is not None
    assert payload["client_name"] == "test_client"

def test_token_persistence(token_manager, temp_data_dir):
    token_info = token_manager.generate_token("persistent_client")
    token_id = token_info["token_id"]

    # Reload token manager
    new_tm = TokenManager(secret_key="test_secret", data_dir=temp_data_dir)
    assert token_id in new_tm.active_tokens
    assert new_tm.active_tokens[token_id]["client_name"] == "persistent_client"

def test_throttled_saving(token_manager):
    token_info = token_manager.generate_token("throttled_client")
    token = token_info["token"]

    # Mock _save_tokens to count calls
    with patch.object(token_manager, '_save_tokens', wraps=token_manager._save_tokens) as mock_save:
        # First call should NOT save because generate_token just saved and set the timer
        token_manager.validate_token(token)
        mock_save.assert_not_called()

        # Manually reset _last_save_time to simulate time passing
        from datetime import datetime
        token_manager._last_save_time = datetime.min

        token_manager.validate_token(token)
        mock_save.assert_called_once()

        # Call again immediately
        mock_save.reset_mock()
        token_manager.validate_token(token)
        mock_save.assert_not_called()

def test_force_save_on_generate(token_manager):
    # Mock _save_tokens
    with patch.object(token_manager, '_save_tokens', wraps=token_manager._save_tokens) as mock_save:
        token_manager.generate_token("new_client")
        mock_save.assert_called_once()

def test_one_time_token_usage_saves(token_manager):
    token_info = token_manager.generate_token("onetime", one_time_use=True)
    token = token_info["token"]

    # Mock _save_tokens
    with patch.object(token_manager, '_save_tokens', wraps=token_manager._save_tokens) as mock_save:
        # validate with mark_as_used=True should trigger save
        token_manager.validate_token(token, mark_as_used=True)
        assert mock_save.call_count >= 1
