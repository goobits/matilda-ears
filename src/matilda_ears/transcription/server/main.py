"""Transcription server entrypoint.

Implementation lives in `matilda_ears.service.transcription_server`.
"""

from ...service.transcription_server import main, start_server

__all__ = ["main", "start_server"]


if __name__ == "__main__":
    main()
