from datetime import datetime
from unittest.mock import patch

from audio_spool import create_spool, list_spools, load_spool, remove_spool
from recorder import TimedWaveSink

CHUNK = 3840


class FakeUser:
    def __init__(self, id, display_name):
        self.id = id
        self.display_name = display_name


def _memory_bytes(sink, user) -> bytes:
    f = sink.audio_data[user].file
    f.seek(0)
    return f.read()


def test_sink_spools_audio_and_survives_reload(tmp_path):
    started = datetime(2026, 10, 27, 9, 30)
    spool = create_spool(tmp_path, 111, 222, started)
    alice = FakeUser(1, "Alice")
    bob = FakeUser(2, "Bob")

    clock = iter([0.0, 1.0, 1.02, 3.0])
    with patch("recorder.time.monotonic", side_effect=lambda: next(clock)):
        sink = TimedWaveSink(spool_dir=spool)
        sink.write(b"\x01" * CHUNK, alice)
        sink.write(b"\x02" * CHUNK, alice)
        sink.write(b"\x03" * CHUNK, bob)

    assert (spool / "meta.json").is_file()
    assert {p.name for p in spool.glob("*.pcm")} == {"1.pcm", "2.pcm"}

    meta, tracks = load_spool(spool)
    assert meta["channel_id"] == 222
    assert meta["started_at"] == started.isoformat()
    assert meta["speakers"] == {"1": "Alice", "2": "Bob"}
    assert tracks["1"] == _memory_bytes(sink, alice)
    assert tracks["2"] == _memory_bytes(sink, bob)
    assert tracks["2"].startswith(b"\x00" * 1000)  # ticho z paddingu je ve spoolu taky


def test_list_and_remove_spool(tmp_path):
    assert list_spools(tmp_path) == []
    spool = create_spool(tmp_path, 111, 222, datetime.now())
    assert list_spools(tmp_path) == [spool]
    assert spool == tmp_path / ".spool" / "111"
    remove_spool(spool)
    assert list_spools(tmp_path) == []
