from discord.voice.gateway import VoiceWebSocket
from discord.voice.receive.reader import AudioReader

from recorder import voice_patch_problems


def test_current_install_is_ok():
    assert voice_patch_problems() == []


def test_missing_update_secret_key(monkeypatch):
    monkeypatch.delattr(AudioReader, "update_secret_key")
    problems = voice_patch_problems()
    assert problems
    assert "update_secret_key" in problems[0]
    assert "py-cord" in problems[0]


def test_patch_not_applied(monkeypatch):
    async def other(self, data):
        pass

    monkeypatch.setattr(VoiceWebSocket, "load_secret_key", other)
    problems = voice_patch_problems()
    assert len(problems) == 1
    assert "není aplikovaný" in problems[0]
