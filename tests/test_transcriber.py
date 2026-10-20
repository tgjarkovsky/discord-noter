import io
from types import SimpleNamespace
from unittest.mock import MagicMock

from transcriber import Segment, format_transcript, transcribe_recording
from voice_alerts import OUTAGE_MARK, Outage


# ---------------------------------------------------------------------------
# format_transcript — čistá funkce, bez externích závislostí
# ---------------------------------------------------------------------------

class TestFormatTranscript:
    def test_empty_segments_returns_placeholder(self):
        assert format_transcript([]) == "(žádný přepis)"

    def test_single_segment(self):
        segments = [Segment(start=0.0, end=2.0, text="Ahoj", username="Alice")]
        result = format_transcript(segments)
        assert "[00:00] **Alice**: Ahoj" in result

    def test_timestamp_minutes_and_seconds(self):
        # 90 sekund → [01:30]
        segments = [Segment(start=90.0, end=92.0, text="Text", username="Alice")]
        result = format_transcript(segments)
        assert "[01:30]" in result

    def test_same_speaker_consecutive_no_repeat_header(self):
        # Stejný mluvčí za sebou → jméno jen jednou
        segments = [
            Segment(start=0.0, end=2.0, text="Věta jedna", username="Alice"),
            Segment(start=2.0, end=4.0, text="Věta dvě", username="Alice"),
        ]
        result = format_transcript(segments)
        assert result.count("**Alice**") == 1
        assert "Věta jedna" in result
        assert "Věta dvě" in result

    def test_different_speakers_each_gets_header(self):
        segments = [
            Segment(start=0.0, end=2.0, text="Ahoj", username="Alice"),
            Segment(start=2.0, end=4.0, text="Nazdar", username="Bob"),
        ]
        result = format_transcript(segments)
        assert "**Alice**" in result
        assert "**Bob**" in result

    def test_alternating_speakers_each_gets_header(self):
        # Alice → Bob → Alice: Alice by měla mít header 2×
        segments = [
            Segment(start=0.0, end=2.0, text="A1", username="Alice"),
            Segment(start=2.0, end=4.0, text="B1", username="Bob"),
            Segment(start=4.0, end=6.0, text="A2", username="Alice"),
        ]
        result = format_transcript(segments)
        assert result.count("**Alice**") == 2
        assert result.count("**Bob**") == 1

    def test_segments_over_one_hour(self):
        # 3700 sekund → [01:41:40] — formát MM:SS, takže [61:40]
        segments = [Segment(start=3700.0, end=3702.0, text="Pozdě", username="Alice")]
        result = format_transcript(segments)
        assert "[61:40]" in result

    def test_preserves_text_content(self):
        segments = [Segment(start=0.0, end=1.0, text="Speciální znaky: & < >", username="Test")]
        result = format_transcript(segments)
        assert "Speciální znaky: & < >" in result


# ---------------------------------------------------------------------------
# transcribe_recording — mockovaný model a sink
# ---------------------------------------------------------------------------

def _audio(pcm: bytes, header: bool = False):
    data = (b"RIFF" + b"\x00" * 40 if header else b"") + pcm
    return SimpleNamespace(file=io.BytesIO(data))


def _model(per_call: list[list[tuple[float, float, str]]]):
    model = MagicMock()
    model.transcribe.side_effect = [
        ([SimpleNamespace(start=a, end=b, text=t) for a, b, t in segs], None) for segs in per_call
    ]
    return model


class _Member:
    def __init__(self, display_name: str):
        self.display_name = display_name


ALICE = _Member("Alice")
BOB = _Member("Bob")


class TestTranscribeRecording:
    def test_merges_users_chronologically(self):
        sink = SimpleNamespace(audio_data={ALICE: _audio(b"\x01" * 2048), BOB: _audio(b"\x01" * 2048)})
        model = _model([[(5.0, 6.0, " druhá ")], [(1.0, 2.0, "první")]])
        result = transcribe_recording(sink, model)
        assert [(s.username, s.text, s.start) for s in result] == [("Bob", "první", 1.0), ("Alice", "druhá", 5.0)]

    def test_skips_short_audio(self):
        sink = SimpleNamespace(audio_data={ALICE: _audio(b"\x01" * 100)})
        model = _model([])
        assert transcribe_recording(sink, model) == []
        model.transcribe.assert_not_called()

    def test_header_only_audio_is_skipped(self):
        # 44B hlavička + 1000B dat → po odříznutí hlavičky < 1024 → přeskočeno
        sink = SimpleNamespace(audio_data={ALICE: _audio(b"\x01" * 1000, header=True)})
        model = _model([])
        assert transcribe_recording(sink, model) == []

    def test_drops_empty_text_and_unknown_source(self):
        sink = SimpleNamespace(audio_data={None: _audio(b"\x01" * 2048)})
        model = _model([[(0.0, 1.0, "  "), (1.0, 2.0, "ahoj")]])
        result = transcribe_recording(sink, model)
        assert [(s.username, s.text) for s in result] == [("Neznámý", "ahoj")]

    def test_uses_czech_and_vad(self):
        sink = SimpleNamespace(audio_data={ALICE: _audio(b"\x01" * 2048)})
        model = _model([[]])
        transcribe_recording(sink, model)
        kwargs = model.transcribe.call_args.kwargs
        assert kwargs["language"] == "cs" and kwargs["vad_filter"] is True


class TestFormatTranscriptOutages:
    def test_outage_inserted_chronologically(self):
        segments = [Segment(10.0, 12.0, "před", "Alice"), Segment(70.0, 72.0, "po", "Alice")]
        result = format_transcript(segments, [Outage(30.0, 65.0, "audio nešlo dešifrovat")])
        lines = [l for l in result.splitlines() if l.strip()]
        assert lines[0].startswith("[00:10] **Alice**: před")
        assert lines[1] == f"[00:30–01:05] {OUTAGE_MARK} (audio nešlo dešifrovat) — řeč v tomto úseku může chybět."
        # po výpadku se jméno mluvčího zopakuje
        assert lines[2].startswith("[01:10] **Alice**: po")

    def test_outage_after_last_segment_and_open_end(self):
        result = format_transcript([Segment(1.0, 2.0, "ahoj", "Bob")], [Outage(90.0, None, "spojení spadlo")])
        assert result.splitlines()[-1].startswith(f"[01:30–konec] {OUTAGE_MARK}")

    def test_outages_without_segments(self):
        assert OUTAGE_MARK in format_transcript([], [Outage(0.0, 5.0, "spojení spadlo")])
