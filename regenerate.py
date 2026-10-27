import re
from pathlib import Path

SUFFIX = "_prepis"


def list_transcripts(notes_dir: str | Path, limit: int = 25) -> list[Path]:
    # Název začíná datem, takže řazení podle názvu = od nejnovějšího
    files = sorted(Path(notes_dir).glob(f"*{SUFFIX}.md"), key=lambda p: p.name, reverse=True)
    return files[:limit]


def notes_path_for(transcript_path: str | Path) -> Path:
    path = Path(transcript_path)
    return path.with_name(path.stem.removesuffix(SUFFIX) + ".md")


def meeting_date_from_name(path: str | Path) -> str:
    match = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})", Path(path).name)
    if not match:
        raise ValueError(f"Název nemá tvar YYYY-MM-DD_HH-MM: {Path(path).name}")
    return f"{match[1]} {match[2]}:{match[3]}"


def resolve_transcript(notes_dir: str | Path, name: str) -> Path | None:
    root = Path(notes_dir).resolve()
    path = (root / name).resolve()
    if path.parent != root or not path.name.endswith(f"{SUFFIX}.md") or not path.is_file():
        return None
    return path
