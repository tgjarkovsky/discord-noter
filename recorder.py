import inspect
import time
from datetime import datetime

import discord
from discord.opus import Decoder
from discord.voice.gateway import VoiceWebSocket

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

_FIX = "Vrať py-cord na commit z requirements.txt nebo uprav patch v recorder.py."


def voice_patch_problems() -> list[str]:
    """České popisy nesouladů mezi reconnect patchem a nainstalovaným py-cordem (prázdný seznam = vše sedí)."""
    from discord.voice.receive.reader import AudioReader, PacketDecryptor

    problems = []
    if VoiceWebSocket.load_secret_key is not _load_secret_key_into_reader:
        problems.append(
            "Patch VoiceWebSocket.load_secret_key není aplikovaný – reconnect voice bude ztrácet audio. "
            "Zkontroluj, že nikdo jiný metodu nepřepisuje po importu recorder.py."
        )
    elif not inspect.iscoroutinefunction(_load_secret_key):
        problems.append(
            "Původní VoiceWebSocket.load_secret_key už není korutina – náš patch ji volá přes await a spadne. " + _FIX
        )
    for cls in (AudioReader, PacketDecryptor):
        if not callable(getattr(cls, "update_secret_key", None)):
            problems.append(
                f"py-cord po updatu nemá {cls.__name__}.update_secret_key – reconnect voice bude ztrácet audio. " + _FIX
            )
    return problems

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
