from __future__ import annotations

import sys
from unittest.mock import patch

from matilda_ears.core import logging as ears_logging


def test_console_logs_use_stderr() -> None:
    ears_logging._stop_listener()
    ears_logging._LOG_QUEUE = None
    try:
        with patch.object(
            ears_logging.logging,
            "StreamHandler",
            wraps=ears_logging.logging.StreamHandler,
        ) as stream_handler:
            listener = ears_logging._ensure_listener(ears_logging.logging.DEBUG, True, False)

        assert listener is not None
        stream_handler.assert_called_once_with(sys.stderr)
    finally:
        ears_logging._stop_listener()
        ears_logging._LOG_QUEUE = None
