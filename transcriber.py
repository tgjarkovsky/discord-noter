import os
import tempfile
import wave
from dataclasses import dataclass

import discord
from faster_whisper import WhisperModel

from voice_alerts import OUTAGE_MARK, Outage


@dataclass
class Segment:
    start: float  # seconds from recording start
    end: float
    text: str
    username: str


def load_model(name: str, device: str = "cpu") -> WhisperModel:
    # "auto" by vybral CUDA i bez nainstalovaných CUDA knihoven (cuBLAS/cuDNN) → pád až při přepisu
    return WhisperModel(name, device=device, compute_type="int8")


def _write_wav(pcm: bytes, path: str) -> None:
    dec = discord.opus.Decoder
    with wave.open(path, "wb") as wf:
        wf.setnchannels(dec.CHANNELS)
        wf.setsampwidth(dec.SAMPLE_SIZE // dec.CHANNELS)
        wf.setframerate(dec.SAMPLING_RATE)
        wf.writeframes(pcm)


def _transcribe_user(model: WhisperModel, pcm: bytes, username: str) -> list[Segment]:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        _write_wav(pcm, tmp_path)
        # vad_filter přeskočí ticho (stopy jsou díky sync_start dorovnané tichem), časy zachová
        segments, _ = model.transcribe(tmp_path, language="cs", vad_filter=True)
        return [
            Segment(start=s.start, end=s.end, text=s.text.strip(), username=username)
            for s in segments
            if s.text.strip()
        ]
    finally:
        os.unlink(tmp_path)


def transcribe_tracks(tracks: dict[str, bytes], model: WhisperModel) -> list[Segment]:
    """Transcribe raw PCM per speaker (klíč = jméno) and return merged chronological segments."""
    all_segments: list[Segment] = []
    for username, raw in tracks.items():
        if len(raw) < 1024:
            continue
        all_segments.extend(_transcribe_user(model, raw, username))

    all_segments.sort(key=lambda s: s.start)
    return all_segments


def transcribe_recording(sink: discord.sinks.Sink, model: WhisperModel) -> list[Segment]:
    """Transcribe each user's audio and return merged chronological segments."""
    tracks: dict[str, bytes] = {}

    # Klíče audio_data jsou User/Member (None = neznámý zdroj)
    for user, audio_data in sink.audio_data.items():
        username = getattr(user, "display_name", None) or "Neznámý"

        audio_data.file.seek(0)
        raw = audio_data.file.read()
        # WaveSink.format_audio uloží audio jako WAV — odřízni hlavičku, _write_wav přidá vlastní
        if raw.startswith(b"RIFF"):
            raw = raw[44:]
        tracks[username] = raw

    return transcribe_tracks(tracks, model)


def _mmss(seconds: float) -> str:
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


def _outage_line(o: Outage) -> str:
    end = _mmss(o.end) if o.end is not None else "konec"
    return f"\n[{_mmss(o.start)}–{end}] {OUTAGE_MARK} ({o.reason}) — řeč v tomto úseku může chybět."


def format_transcript(segments: list[Segment], outages: list[Outage] = ()) -> str:
    """Format segments into readable transcript, with audio outages marked in place."""
    if not segments and not outages:
        return "(žádný přepis)"

    pending = sorted(outages, key=lambda o: o.start)
    lines = []
    prev_user = None
    for seg in segments:
        while pending and pending[0].start <= seg.start:
            lines.append(_outage_line(pending.pop(0)))
            prev_user = None

        if seg.username != prev_user:
            lines.append(f"\n[{_mmss(seg.start)}] **{seg.username}**: {seg.text}")
            prev_user = seg.username
        else:
            lines.append(f"  {seg.text}")

    lines.extend(_outage_line(o) for o in pending)
    return "\n".join(lines).strip()
