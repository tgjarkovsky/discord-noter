import logging
from pathlib import Path

import anthropic

from voice_alerts import OUTAGE_MARK

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"
TRUNCATED_NOTE = "\n\n> ⚠️ Zápis byl zkrácen — dosažen limit délky odpovědi."

ACTION_ITEMS_INSTRUCTIONS = """Sekce `## Akční body` jako Markdown tabulka se sloupci:
  | Vlastník | Úkol | Termín |
  | --- | --- | --- |
  Vlastník je jméno mluvčího z přepisu; když úkol nikdo nepřevzal, napiš „neurčeno“.
  Termín uveď jen ten, který zazněl; jinak napiš „neuvedeno“, termín si nedomýšlej.
  Když nevznikly žádné akční body, napiš pod nadpis „Žádné akční body.“ (bez tabulky).
  Tento formát akčních bodů má přednost před stylem vzorových zápisů."""


def _read_style_file(f: Path) -> str | None:
    raw = f.read_bytes()
    for encoding in ("utf-8-sig", "cp1250"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    log.warning("Vzor %s nejde přečíst jako UTF-8 ani cp1250, přeskakuji", f.name)
    return None


def _read_existing_notes(folder: str, max_files: int = 5) -> str:
    """Read the most recent .md files from folder as style examples."""
    path = Path(folder)
    if not path.exists() or not path.is_dir():
        return ""

    md_files = sorted(path.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not md_files:
        return ""

    parts = []
    for f in md_files[:max_files]:
        content = _read_style_file(f)
        if content is None:
            continue
        parts.append(f"--- {f.name} ---\n{content}")

    return "\n\n".join(parts)


def generate_notes(
    transcript: str,
    meeting_date: str,
    existing_notes_folder: str | None,
    api_key: str,
    model: str | None = None,
) -> str:
    """Generate meeting notes from transcript using Claude."""

    client = anthropic.Anthropic(api_key=api_key)

    style_section = ""
    if existing_notes_folder:
        existing = _read_existing_notes(existing_notes_folder)
        if existing:
            style_section = f"""
## Příklady existujících zápisů (použij stejný styl a úroveň detailu):

{existing}

---
"""

    outage_section = ""
    if OUTAGE_MARK in transcript:
        outage_section = f"""
- Výpadky záznamu: přepis obsahuje řádky „{OUTAGE_MARK}“ s časovým úsekem. Hned pod nadpis zápisu
  dej upozornění „⚠️ Záznam má výpadky: <úseky>“. Co v těchto úsecích chybí, si nedomýšlej."""

    prompt = f"""Jsi asistent pro tvorbu zápisů z porad. Vytvoř strukturovaný zápis z porady v češtině.
{style_section}
## Přepis porady ({meeting_date}):

{transcript}

---

Vytvoř zápis z porady ve formátu Markdown. Zápis musí obsahovat:
- Datum a čas
- Seznam účastníků (přesně ti, kteří mluví v přepisu)
- Hlavní témata diskuse
- Klíčová rozhodnutí
- {ACTION_ITEMS_INSTRUCTIONS}
- Detailní shrnutí co kdo říkal — přiřaď výroky konkrétním osobám{outage_section}

Buď věcný a přesný. Nedomýšlej věci, které nebyly řečeny."""

    message = client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    log.info(
        f"Claude {message.model}: vstup {message.usage.input_tokens} tokenů, "
        f"výstup {message.usage.output_tokens} tokenů"
    )

    text = message.content[0].text
    if message.stop_reason == "max_tokens":
        text += TRUNCATED_NOTE
    return text
