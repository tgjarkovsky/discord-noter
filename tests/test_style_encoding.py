import logging

from notes_generator import _read_existing_notes


def test_cp1250_and_utf8_files_are_both_read(tmp_path):
    (tmp_path / "stary.md").write_bytes("Příliš žluťoučký kůň".encode("cp1250"))
    (tmp_path / "novy.md").write_text("Úkoly: řešit šíření", encoding="utf-8")

    result = _read_existing_notes(str(tmp_path))

    assert "Příliš žluťoučký kůň" in result
    assert "Úkoly: řešit šíření" in result


def test_utf8_bom_is_stripped(tmp_path):
    (tmp_path / "bom.md").write_bytes(b"\xef\xbb\xbf" + "Zápis ěšč".encode("utf-8"))

    result = _read_existing_notes(str(tmp_path))

    assert "﻿" not in result
    assert "Zápis ěšč" in result


def test_undecodable_file_is_skipped(tmp_path, caplog):
    (tmp_path / "rozbity.md").write_bytes(b"\x81\x8d\x8f\x90\x9d")
    (tmp_path / "ok.md").write_text("Platný zápis", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        result = _read_existing_notes(str(tmp_path))

    assert "Platný zápis" in result
    assert "rozbity.md" in caplog.text
