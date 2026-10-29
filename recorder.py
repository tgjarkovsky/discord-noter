import time
from datetime import datetime

import discord
from discord.opus import Decoder
from discord.voice.gateway import VoiceWebSocket

from voice_alerts import outages

_load_secret_key = VoiceWebSocket.load_secret_key


async def _load_secret_key_into_reader(self, data):
    """Po reconnectu voice websocketu pošle nový klíč i běžícímu AudioReaderu.

    py-cord (2.8.2.dev91) klíč uloží jen na websocket, reader dál dešifruje starým
    a od reconnectu se ztratí veškeré audio (CryptoError: Decryption failed).
    """
    await _load_secret_key(self, data)
    reader = getattr(self.state.client, "_reader", None)
    if reader:
        reader.update_secret_key(bytes(data["secret_key"]))


VoiceWebSocket.load_secret_key = _load_secret_key_into_reader

BYTES_PER_SEC = Decoder.SAMPLING_RATE * Decoder.SAMPLE_SIZE
MIN_GAP = BYTES_PER_SEC // 10  # 100 ms — menší mezery jsou jen jitter


def padding_needed(elapsed: float, written: int, chunk_len: int) -> int:
    """Kolik bajtů ticha vložit, aby chunk začínal v čase `elapsed` od startu nahrávání."""
    gap = int(elapsed * BYTES_PER_SEC) - chunk_len - written
    if gap < MIN_GAP:
        return 0
    return gap - gap % Decoder.SAMPLE_SIZE


class TimedWaveSink(discord.sinks.WaveSink):
    """WaveSink, který dorovná každou stopu tichem podle reálného času.

    py-cord (od 2.7) ticho mezi promluvami ani před první promluvou nedoplňuje,
    takže bez toho by časové značky i pořadí mluvčích v přepisu nesouhlasily.
    """

    # ponytail: čas příchodu paketů ≈ čas promluvy; jitter pod MIN_GAP se ignoruje

    def __init__(self):
        super().__init__()
        self._start = time.monotonic()
        self.started_at = datetime.now()
        self._written: dict = {}
        self.speech: dict = {}  # user -> bajty skutečně přijaté řeči (bez paddingu)
        self.marks: list[tuple[float, str]] = []  # (s od startu, druh problému) — viz voice_alerts

    def mark(self, kind: str) -> None:
        self.marks.append((time.monotonic() - self._start, kind))

    def write(self, data, user):
        pcm = data.pcm if hasattr(data, "pcm") else data
        written = self._written.get(user, 0)
        pad = padding_needed(time.monotonic() - self._start, written, len(pcm))
        if pad:
            super().write(b"\x00" * pad, user)
        super().write(pcm, user)
        self._written[user] = written + pad + len(pcm)
        self.speech[user] = self.speech.get(user, 0) + len(pcm)


def _fmt_duration(seconds: float) -> str:
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    return f"{minutes} min {secs} s" if minutes else f"{secs} s"


def status_message(sink: TimedWaveSink, now_monotonic: float | None = None) -> str:
    """Text pro /note-status: délka nahrávání, zachycená řeč podle mluvačů a výpadky."""
    now = time.monotonic() if now_monotonic is None else now_monotonic
    lines = [f"🔴 Nahrávám už {_fmt_duration(now - sink._start)}."]
    if sink.speech:
        lines.append("**Zachycená řeč:**")
        for user, size in sorted(sink.speech.items(), key=lambda kv: kv[1], reverse=True):
            name = getattr(user, "display_name", None) or str(user)
            lines.append(f"- {name}: {_fmt_duration(size / BYTES_PER_SEC)}")
    else:
        lines.append("⚠️ Zatím jsem nezachytil žádný hlas – zkontroluj oprávnění a že mluvíte ve správném kanálu.")
    for o in outages(sink.marks):
        end = _fmt_duration(o.end) if o.end is not None else "doteď"
        lines.append(f"⚠️ Výpadek audia {_fmt_duration(o.start)} – {end} ({o.reason})")
    return "\n".join(lines)
