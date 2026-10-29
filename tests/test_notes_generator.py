import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from notes_generator import _read_existing_notes, generate_notes
from voice_alerts import OUTAGE_MARK


# ---------------------------------------------------------------------------
# _read_existing_notes — filesystem, bez externích deps
# ---------------------------------------------------------------------------

class TestReadExistingNotes:
    def test_nonexistent_path_returns_empty(self, tmp_path):
        assert _read_existing_notes(str(tmp_path / "no_such_dir")) == ""

    def test_path_is_file_not_dir_returns_empty(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello")
        assert _read_existing_notes(str(f)) == ""

    def test_empty_directory_returns_empty(self, tmp_path):
        assert _read_existing_notes(str(tmp_path)) == ""

    def test_directory_without_md_files_returns_empty(self, tmp_path):
        (tmp_path / "note.txt").write_text("text")
        assert _read_existing_notes(str(tmp_path)) == ""

    def test_reads_single_md_file(self, tmp_path):
        (tmp_path / "note.md").write_text("# Obsah\nNějaký text", encoding="utf-8")
        result = _read_existing_notes(str(tmp_path))
        assert "note.md" in result
        assert "Nějaký text" in result

    def test_reads_multiple_md_files(self, tmp_path):
        (tmp_path / "a.md").write_text("# A", encoding="utf-8")
        (tmp_path / "b.md").write_text("# B", encoding="utf-8")
        result = _read_existing_notes(str(tmp_path))
        assert "# A" in result
        assert "# B" in result

    def test_respects_max_files_limit(self, tmp_path):
        for i in range(7):
            (tmp_path / f"note{i:02d}.md").write_text(f"# Note {i}", encoding="utf-8")
        result = _read_existing_notes(str(tmp_path), max_files=3)
        # Každý soubor dává sekci "--- filename ---\ncontent", max_files=3 → 3 sekce
        assert result.count("--- note") == 3

    def test_includes_filename_as_separator(self, tmp_path):
        (tmp_path / "meeting.md").write_text("content", encoding="utf-8")
        result = _read_existing_notes(str(tmp_path))
        assert "--- meeting.md ---" in result


# ---------------------------------------------------------------------------
# generate_notes — mockovaný Anthropic client
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_anthropic_client():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="# Zápis\n\nObsah zápisu")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    return mock_client


class TestGenerateNotes:
    def test_returns_text_from_api(self, mock_anthropic_client):
        with patch("notes_generator.anthropic.Anthropic", return_value=mock_anthropic_client):
            result = generate_notes(
                transcript="Ahoj, jak se máš?",
                meeting_date="2024-03-25 14:00",
                existing_notes_folder=None,
                api_key="test-key",
            )
        assert result == "# Zápis\n\nObsah zápisu"

    def test_transcript_included_in_prompt(self, mock_anthropic_client):
        with patch("notes_generator.anthropic.Anthropic", return_value=mock_anthropic_client):
            generate_notes(
                transcript="Unikátní přepis ABC123",
                meeting_date="2024-03-25",
                existing_notes_folder=None,
                api_key="test-key",
            )
        call_args = mock_anthropic_client.messages.create.call_args
        messages = call_args[1]["messages"]
        assert "Unikátní přepis ABC123" in messages[0]["content"]

    def test_meeting_date_included_in_prompt(self, mock_anthropic_client):
        with patch("notes_generator.anthropic.Anthropic", return_value=mock_anthropic_client):
            generate_notes(
                transcript="text",
                meeting_date="2026-03-25 10:00",
                existing_notes_folder=None,
                api_key="test-key",
            )
        call_args = mock_anthropic_client.messages.create.call_args
        messages = call_args[1]["messages"]
        assert "2026-03-25 10:00" in messages[0]["content"]

    def test_no_style_section_when_folder_is_none(self, mock_anthropic_client):
        with patch("notes_generator.anthropic.Anthropic", return_value=mock_anthropic_client):
            generate_notes("text", "2024-03-25", None, "key")
        call_args = mock_anthropic_client.messages.create.call_args
        messages = call_args[1]["messages"]
        assert "Příklady existujících zápisů" not in messages[0]["content"]

    def test_style_section_included_when_notes_exist(self, mock_anthropic_client, tmp_path):
        (tmp_path / "old.md").write_text("# Starý zápis\nObsah", encoding="utf-8")
        with patch("notes_generator.anthropic.Anthropic", return_value=mock_anthropic_client):
            generate_notes("text", "2024-03-25", str(tmp_path), "key")
        call_args = mock_anthropic_client.messages.create.call_args
        messages = call_args[1]["messages"]
        assert "Příklady existujících zápisů" in messages[0]["content"]
        assert "Starý zápis" in messages[0]["content"]

    def test_no_style_section_when_folder_has_no_md_files(self, mock_anthropic_client, tmp_path):
        # Složka existuje ale nemá .md soubory → žádná style sekce
        with patch("notes_generator.anthropic.Anthropic", return_value=mock_anthropic_client):
            generate_notes("text", "2024-03-25", str(tmp_path), "key")
        call_args = mock_anthropic_client.messages.create.call_args
        messages = call_args[1]["messages"]
        assert "Příklady existujících zápisů" not in messages[0]["content"]

    def test_api_called_with_correct_model(self, mock_anthropic_client):
        with patch("notes_generator.anthropic.Anthropic", return_value=mock_anthropic_client):
            generate_notes("text", "2024-03-25", None, "key")
        call_args = mock_anthropic_client.messages.create.call_args
        assert call_args[1]["model"] == "claude-sonnet-4-6"

    def test_custom_model(self, mock_anthropic_client):
        with patch("notes_generator.anthropic.Anthropic", return_value=mock_anthropic_client):
            generate_notes("text", "2024-03-25", None, "key", model="claude-sonnet-5")
        assert mock_anthropic_client.messages.create.call_args[1]["model"] == "claude-sonnet-5"

    def test_truncated_response_gets_warning(self, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value.stop_reason = "max_tokens"
        with patch("notes_generator.anthropic.Anthropic", return_value=mock_anthropic_client):
            result = generate_notes("text", "2024-03-25", None, "key")
        assert result.startswith("# Zápis") and "zkrácen" in result

    def test_logs_token_usage(self, mock_anthropic_client, caplog):
        resp = mock_anthropic_client.messages.create.return_value
        resp.model = "claude-sonnet-4-6"
        resp.usage.input_tokens = 12345
        resp.usage.output_tokens = 678
        with caplog.at_level("INFO", logger="notes_generator"):
            with patch("notes_generator.anthropic.Anthropic", return_value=mock_anthropic_client):
                generate_notes("text", "2024-03-25", None, "key")
        assert "vstup 12345 tokenů, výstup 678 tokenů" in caplog.text

    def test_complete_response_has_no_warning(self, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value.stop_reason = "end_turn"
        with patch("notes_generator.anthropic.Anthropic", return_value=mock_anthropic_client):
            result = generate_notes("text", "2024-03-25", None, "key")
        assert "zkrácen" not in result

    @pytest.mark.parametrize("with_samples", [False, True])
    def test_akcni_body_instructions_in_prompt(self, mock_anthropic_client, tmp_path, with_samples):
        if with_samples:
            (tmp_path / "old.md").write_text("# Starý zápis\n- Úkoly: Petr zavolá", encoding="utf-8")
        folder = str(tmp_path) if with_samples else None
        with patch("notes_generator.anthropic.Anthropic", return_value=mock_anthropic_client):
            generate_notes("text", "2024-03-25", folder, "key")
        prompt = mock_anthropic_client.messages.create.call_args[1]["messages"][0]["content"]
        assert ("Příklady existujících zápisů" in prompt) == with_samples
        for expected in ("## Akční body", "Vlastník | Úkol | Termín", "neurčeno", "neuvedeno", "Žádné akční body."):
            assert expected in prompt

    def test_outage_instructions_only_when_transcript_has_outage(self, mock_anthropic_client):
        with patch("notes_generator.anthropic.Anthropic", return_value=mock_anthropic_client):
            generate_notes("bez problémů", "2026-10-20", None, "key")
            generate_notes(f"[00:30–01:05] {OUTAGE_MARK} (x)", "2026-10-20", None, "key")
        prompts = [c[1]["messages"][0]["content"] for c in mock_anthropic_client.messages.create.call_args_list]
        assert "Výpadky záznamu" not in prompts[0]
        assert "Výpadky záznamu" in prompts[1]
