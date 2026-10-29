from unittest.mock import patch

from recorder import BYTES_PER_SEC, TimedWaveSink, status_message


def _sink():
    with patch("recorder.time.monotonic", return_value=100.0):
        return TimedWaveSink()


def test_speech_per_user():
    sink = _sink()
    with patch("recorder.time.monotonic", return_value=102.0):
        sink.write(b"\x01\x00" * (BYTES_PER_SEC), "alice")
    text = status_message(sink, now_monotonic=165.0)
    assert "1 min 5 s" in text
    assert "alice: 2 s" in text
    assert "bob" not in text


def test_no_voice_warning():
    assert "nezachytil žádný hlas" in status_message(_sink(), now_monotonic=105.0)


def test_outage():
    sink = _sink()
    sink.marks = [(10.0, "disconnect"), (15.0, "reconnected")]
    text = status_message(sink, now_monotonic=130.0)
    assert "Výpadek audia 10 s – 15 s" in text
