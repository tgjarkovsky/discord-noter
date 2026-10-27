from datetime import datetime
from unittest.mock import patch

from recorder import BYTES_PER_SEC, MIN_GAP, TimedWaveSink, padding_needed

CHUNK = 3840  # 20 ms stereo s16 @ 48 kHz


class TestPaddingNeeded:
    def test_first_chunk_after_two_seconds(self):
        pad = padding_needed(2.0, 0, CHUNK)
        assert pad == 2 * BYTES_PER_SEC - CHUNK

    def test_continuous_speech_no_padding(self):
        # Zapsáno přesně tolik, kolik odpovídá času → žádná mezera
        assert padding_needed(1.0, BYTES_PER_SEC - CHUNK, CHUNK) == 0

    def test_small_jitter_ignored(self):
        assert padding_needed(1.0, BYTES_PER_SEC - CHUNK - (MIN_GAP - 4), CHUNK) == 0

    def test_ahead_of_time_no_padding(self):
        assert padding_needed(1.0, 2 * BYTES_PER_SEC, CHUNK) == 0

    def test_padding_is_frame_aligned(self):
        assert padding_needed(1.2345678, 0, CHUNK) % 4 == 0


class TestTimedWaveSink:
    def test_started_at_is_creation_time(self):
        sink = TimedWaveSink()
        assert isinstance(sink.started_at, datetime)
        assert abs((datetime.now() - sink.started_at).total_seconds()) < 5

    def test_tracks_are_aligned_to_wall_clock(self):
        clock = iter([0.0, 1.0, 1.02, 3.0])
        with patch("recorder.time.monotonic", side_effect=lambda: next(clock)):
            sink = TimedWaveSink()  # start = 0.0
            sink.write(b"\x01" * CHUNK, "alice")  # t=1.0 → 1 s ticha
            sink.write(b"\x01" * CHUNK, "alice")  # t=1.02 → souvislá řeč
            sink.write(b"\x01" * CHUNK, "bob")  # t=3.0 → 3 s ticha
        alice = sink.audio_data["alice"].file.getvalue()
        bob = sink.audio_data["bob"].file.getvalue()
        assert len(alice) == BYTES_PER_SEC + CHUNK
        assert alice[: BYTES_PER_SEC - CHUNK] == b"\x00" * (BYTES_PER_SEC - CHUNK)
        assert len(bob) == 3 * BYTES_PER_SEC
