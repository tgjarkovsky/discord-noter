from pathlib import Path

# Projekt = podsložka styles/ se vzorovými zápisy (.md). Složka není v gitu (repo je veřejné),
# do týmu se šíří s instalačním balíčkem.
STYLES_DIR = Path(__file__).parent / "styles"


def list_projects() -> list[str]:
    if not STYLES_DIR.is_dir():
        return []
    return sorted(d.name for d in STYLES_DIR.iterdir() if d.is_dir())


def style_folder(name: str) -> str:
    return str(STYLES_DIR / name)
