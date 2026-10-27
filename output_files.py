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


def write_notes(base: Path, notes: str) -> Path:
    path = base.with_name(base.name + ".md")
    path.write_text(notes, encoding="utf-8")
    return path
