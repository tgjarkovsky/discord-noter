from pathlib import Path

from regenerate import list_transcripts, meeting_date_from_name, notes_path_for, resolve_transcript


def test_list_transcripts_filters_sorts_and_limits(tmp_path):
    for name in ["2026-03-01_10-00_prepis.md", "2026-03-03_10-00_prepis.md", "2026-03-02_10-00_prepis.md",
                 "2026-03-03_10-00.md", "x.txt"]:
        (tmp_path / name).write_text("x", encoding="utf-8")
    names = [p.name for p in list_transcripts(tmp_path)]
    assert names == ["2026-03-03_10-00_prepis.md", "2026-03-02_10-00_prepis.md", "2026-03-01_10-00_prepis.md"]
    assert len(list_transcripts(tmp_path, limit=2)) == 2


def test_notes_path_for():
    assert notes_path_for(Path("2026-03-25_14-30_Tym_prepis.md")) == Path("2026-03-25_14-30_Tym.md")


def test_meeting_date_from_name():
    assert meeting_date_from_name(Path("2026-03-25_14-30_Tym_prepis.md")) == "2026-03-25 14:30"


def test_resolve_transcript(tmp_path):
    (tmp_path / "a_prepis.md").write_text("x", encoding="utf-8")
    (tmp_path.parent / "x_prepis.md").write_text("x", encoding="utf-8")
    assert resolve_transcript(tmp_path, "a_prepis.md") == (tmp_path / "a_prepis.md").resolve()
    assert resolve_transcript(tmp_path, "../x_prepis.md") is None
    assert resolve_transcript(tmp_path, "missing_prepis.md") is None
