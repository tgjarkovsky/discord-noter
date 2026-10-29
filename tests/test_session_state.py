from datetime import datetime

from session_state import interrupted_message, mark_finished, mark_started, pop_interrupted

START = datetime(2026, 10, 27, 14, 5)


def test_unfinished_recording_is_returned_and_file_removed(tmp_path):
    path = tmp_path / ".active_recordings.json"
    mark_started(path, 1, 10, START)
    records = pop_interrupted(path)
    assert len(records) == 1
    assert records[0]["guild_id"] == 1
    assert records[0]["channel_id"] == 10
    assert datetime.fromisoformat(records[0]["started_at"]) == START
    assert not path.exists()


def test_finished_recording_is_not_returned(tmp_path):
    path = tmp_path / ".active_recordings.json"
    mark_started(path, 1, 10, START)
    mark_finished(path, 1)
    assert pop_interrupted(path) == []


def test_concurrent_guilds_do_not_overwrite(tmp_path):
    path = tmp_path / ".active_recordings.json"
    mark_started(path, 1, 10, START)
    mark_started(path, 2, 20, START)
    mark_finished(path, 1)
    assert [r["guild_id"] for r in pop_interrupted(path)] == [2]


def test_corrupt_or_missing_file_gives_empty_list(tmp_path):
    path = tmp_path / ".active_recordings.json"
    assert pop_interrupted(path) == []
    path.write_text("{nejson", encoding="utf-8")
    assert pop_interrupted(path) == []


def test_message_contains_start_time(tmp_path):
    path = tmp_path / ".active_recordings.json"
    mark_started(path, 1, 10, START)
    assert "14:05" in interrupted_message(pop_interrupted(path)[0])
