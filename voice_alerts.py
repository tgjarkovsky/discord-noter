import logging
import math
import time
from dataclasses import dataclass

COOLDOWN = 60  # s — stejné upozornění nejvýš jednou za tuto dobu
MERGE_GAP = 5  # s — audio chyby bližší k sobě patří do jednoho výpadku
# Pár vadných paketů při přechodu na DAVE je běžné (25 ≈ 0,5 s audia)
MIN_AUDIO_ERRORS = 25
OUTAGE_MARK = "⚠️ **Výpadek audia**"

# podřetězec logu py-cordu → druh události
KINDS = {
    "Disconnected from voice": "disconnect",
    "Voice connection completed": "reconnected",
    "CryptoError while decoding": "crypto",
    "Opus decode failed": "opus",
}

# druh → (zpráva do chatu, kolik výskytů za COOLDOWN je už problém)
ALERTS = {
    "disconnect": ("⚠️ Spojení s voice kanálem spadlo, připojuji se znovu…", 1),
    "crypto": ("⚠️ Audio se nedaří dešifrovat — nahrávka může mít díry.", MIN_AUDIO_ERRORS),
    "opus": ("⚠️ Část audia se nedaří dekódovat — nahrávka může mít výpadky.", MIN_AUDIO_ERRORS),
}

REASONS = {
    "disconnect": "spojení spadlo",
    "crypto": "audio nešlo dešifrovat",
    "opus": "audio nešlo dekódovat",
}


@dataclass
class Outage:
    start: float  # s od začátku nahrávky
    end: float | None  # None = do konce nahrávky
    reason: str


class ChatAlertHandler(logging.Handler):
    """Přeposílá problémy s voice spojením z logu py-cordu do chatu přes `send(text)`
    a každou událost hlásí přes `mark(kind)`, aby šla vyznačit v přepisu.

    `send` i `mark` musí být thread-safe — py-cord loguje i z vlákna, které čte audio.
    """

    def __init__(self, send, mark=lambda kind: None):
        super().__init__(logging.INFO)
        self._send = send
        self._mark = mark
        self._hits: dict[str, tuple[float, int]] = {}
        self._sent: dict[str, float] = {}

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        kind = next((k for needle, k in KINDS.items() if needle in msg), None)
        if kind is None:
            return
        self._mark(kind)
        if kind in ALERTS:
            self._alert(kind)

    def _alert(self, kind: str) -> None:
        text, min_count = ALERTS[kind]
        now = time.monotonic()

        start, count = self._hits.get(kind, (now, 0))
        if now - start > COOLDOWN:
            start, count = now, 0
        self._hits[kind] = (start, count + 1)

        if count + 1 < min_count or now - self._sent.get(kind, -math.inf) < COOLDOWN:
            return
        self._sent[kind] = now
        self._send(text)


def outages(marks: list[tuple[float, str]]) -> list[Outage]:
    """Z událostí (čas, druh) složí úseky nahrávky, kde chybí audio."""
    result: list[Outage] = []
    down_since: float | None = None
    burst: list[tuple[float, str]] = []

    def flush_burst():
        if len(burst) >= MIN_AUDIO_ERRORS:
            result.append(Outage(burst[0][0], burst[-1][0], REASONS[burst[0][1]]))
        burst.clear()

    for t, kind in sorted(marks):
        if kind == "disconnect":
            down_since = t if down_since is None else down_since
        elif kind == "reconnected":
            if down_since is not None:
                result.append(Outage(down_since, t, REASONS["disconnect"]))
                down_since = None
        else:
            if burst and t - burst[-1][0] > MERGE_GAP:
                flush_burst()
            burst.append((t, kind))
    flush_burst()
    if down_since is not None:
        result.append(Outage(down_since, None, REASONS["disconnect"]))
    return sorted(result, key=lambda o: o.start)
