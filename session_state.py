import json
from datetime import datetime
from pathlib import Path


def _read(path: Path) -> dict[str, dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(path: Path, data: dict[str, dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def mark_started(path: Path, guild_id: int, channel_id: int, started_at: datetime) -> None:
    data = _read(path)
    data[str(guild_id)] = {
        "guild_id": guild_id,
        "channel_id": channel_id,
        "started_at": started_at.isoformat(),
    }
    _write(path, data)


def mark_finished(path: Path, guild_id: int) -> None:
    data = _read(path)
    if data.pop(str(guild_id), None) is not None:
        _write(path, data)


def pop_interrupted(path: Path) -> list[dict]:
    data = _read(path)
    try:
        Path(path).unlink()
    except OSError:
        pass
    return [r for r in data.values() if isinstance(r, dict) and {"guild_id", "channel_id", "started_at"} <= r.keys()]


def interrupted_message(record: dict) -> str:
    try:
        started = datetime.fromisoformat(record["started_at"]).strftime("%H:%M")
    except (KeyError, ValueError):
        started = "neznámo kdy"
    return (
        f"⚠️ Bot spadl nebo byl vypnut během nahrávání, které začalo v {started}. "
        "Audio z této porady se nepodařilo zachránit. Spusť nové nahrávání přes /note-start."
    )
