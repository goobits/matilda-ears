from unittest.mock import Mock

from matilda_ears.audio.internal.capture import PipeBasedAudioStreamer


class FakeProcess:
    def __init__(self) -> None:
        self.running = True
        self.stdout = Mock()

    def poll(self):
        return None if self.running else 0

    def terminate(self) -> None:
        self.running = False

    def wait(self, timeout=None) -> int:
        self.running = False
        return 0

    def kill(self) -> None:
        self.running = False


def test_stop_recording_is_idempotent_and_releases_process_state() -> None:
    streamer = PipeBasedAudioStreamer(loop=Mock(), queue=Mock())
    process = FakeProcess()
    streamer.arecord_process = process
    streamer.reader_thread = Mock(is_alive=Mock(return_value=False))
    streamer.stats.update_chunk(512, timestamp=1.0)

    first = streamer.stop_recording()
    second = streamer.stop_recording()

    assert first == second
    assert first["chunks_sent"] == 1
    assert streamer.arecord_process is None
    assert streamer.reader_thread is None
    assert streamer._stop_event.is_set()
