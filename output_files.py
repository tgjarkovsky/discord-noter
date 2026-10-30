import re
from datetime import datetime
from pathlib import Path


def output_base(output_dir: str, project_name: str | None, when: datetime) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    name = when.strftime("%Y-%m-%d_%H-%M")
    if project_name:
        name += "_" + re.sub(r"[^\w-]+", "_", project_name).strip("_")
    return directory / name


def write_transcript(base: Path, transcript: str) -> Path:
    path = base.with_name(base.name + "_prepis.md")
    path.write_text(transcript, encoding="utf-8")
    return path


def write_audio(base: Path, sink) -> list[Path]:
    """Záloha audia do WAV, když přepis selže. Stopy kratší než 1024 B PCM se přeskočí."""
    from transcriber import _write_wav

    paths = []
    for user, audio_data in sink.audio_data.items():
        audio_data.file.seek(0)
        raw = audio_data.file.read()
        if raw.startswith(b"RIFF"):
            raw = raw[44:]
        if len(raw) < 1024:
            continue
        name = getattr(user, "display_name", None) or "Neznamy"
        name = re.sub(r"[^\w-]+", "_", name).strip("_") or "Neznamy"
        path = base.with_name(f"{base.name}_audio_{name}.wav")
        _write_wav(raw, str(path))
        paths.append(path)
    return paths


def write_notes(base: Path, notes: str) -> Path:
    path = base.with_name(base.name + ".md")
    path.write_text(notes, encoding="utf-8")
    return path
