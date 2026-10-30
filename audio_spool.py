import json
import re
import shutil
from datetime import datetime
from pathlib import Path


def _meta_path(spool_dir: Path) -> Path:
    return spool_dir / "meta.json"


def _safe_name(user_key: str) -> str:
    return re.sub(r"[^\w.-]", "_", str(user_key))


def create_spool(root, guild_id: int, channel_id: int, started_at: datetime) -> Path:
    spool_dir = Path(root) / ".spool" / str(guild_id)
    if spool_dir.exists():
        shutil.rmtree(spool_dir)
    spool_dir.mkdir(parents=True)
    meta = {"channel_id": channel_id, "started_at": started_at.isoformat(), "speakers": {}}
    _meta_path(spool_dir).write_text(json.dumps(meta), encoding="utf-8")
    return spool_dir


def append_track(spool_dir: Path, user_key: str, username: str, pcm: bytes) -> None:
    key = _safe_name(user_key)
    meta = json.loads(_meta_path(spool_dir).read_text(encoding="utf-8"))
    if meta["speakers"].get(key) != username:
        meta["speakers"][key] = username
        _meta_path(spool_dir).write_text(json.dumps(meta), encoding="utf-8")
    with open(spool_dir / f"{key}.pcm", "ab") as f:
        f.write(pcm)


def load_spool(spool_dir: Path) -> tuple[dict, dict[str, bytes]]:
    meta = json.loads(_meta_path(spool_dir).read_text(encoding="utf-8"))
    tracks = {p.stem: p.read_bytes() for p in sorted(spool_dir.glob("*.pcm"))}
    return meta, tracks


def list_spools(root) -> list[Path]:
    base = Path(root) / ".spool"
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if _meta_path(p).is_file())


def remove_spool(spool_dir: Path) -> None:
    shutil.rmtree(spool_dir, ignore_errors=True)
