from datetime import datetime

from output_files import output_base, write_notes, write_transcript

WHEN = datetime(2026, 10, 27, 14, 5)


def test_name_contains_date(tmp_path):
    assert output_base(str(tmp_path), None, WHEN).name == "2026-10-27_14-05"


def test_project_is_sanitized(tmp_path):
    base = output_base(str(tmp_path), "Tým / A", WHEN)
    assert base.name == "2026-10-27_14-05_Tým_A"
    assert base.parent == tmp_path


def test_creates_output_dir(tmp_path):
    out = tmp_path / "new" / "dir"
    output_base(str(out), None, WHEN)
    assert out.is_dir()


def test_write_transcript_utf8(tmp_path):
    base = output_base(str(tmp_path), "Tým", WHEN)
    path = write_transcript(base, "Příliš žluťoučký kůň")
    assert path.name == "2026-10-27_14-05_Tým_prepis.md"
    assert path.read_text(encoding="utf-8") == "Příliš žluťoučký kůň"


def test_write_notes_utf8(tmp_path):
    base = output_base(str(tmp_path), "Tým", WHEN)
    path = write_notes(base, "Zápis ěšč")
    assert path.name == "2026-10-27_14-05_Tým.md"
    assert path.read_text(encoding="utf-8") == "Zápis ěšč"
