import io
import wave
from types import SimpleNamespace

from output_files import write_audio


class _User:
    def __init__(self, display_name):
        self.display_name = display_name


def _track(n_bytes):
    return SimpleNamespace(file=io.BytesIO(b"\x01\x00" * (n_bytes // 2)))


def test_write_audio_saves_readable_wav_and_skips_short(tmp_path):
    sink = SimpleNamespace(audio_data={
        _User("Jan Novák"): _track(48000),
        None: _track(2048),
        _User("Krátký"): _track(100),
    })
    paths = write_audio(tmp_path / "porada", sink)

    assert sorted(p.name for p in paths) == ["porada_audio_Jan_Novák.wav", "porada_audio_Neznamy.wav"]
    with wave.open(str(tmp_path / "porada_audio_Jan_Novák.wav")) as wf:
        assert wf.getnframes() == 48000 // (wf.getsampwidth() * wf.getnchannels())
    assert not (tmp_path / "porada_audio_Krátký.wav").exists()
