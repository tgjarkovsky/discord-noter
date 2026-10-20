import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import nacl.secret
import nacl.utils
from discord.voice.gateway import VoiceWebSocket
from discord.voice.receive.reader import PacketDecryptor

import recorder  # noqa: F401  — aplikuje patch

MODE = "aead_xchacha20_poly1305_rtpsize"


def _ws_with_reader(old_key: bytes):
    decryptor = PacketDecryptor(MODE, old_key, None)
    reader = SimpleNamespace(update_secret_key=decryptor.update_secret_key)
    state = SimpleNamespace(channel_id=1, guild_id=2, secret_key=list(old_key), client=SimpleNamespace(_reader=reader))
    ws = VoiceWebSocket.__new__(VoiceWebSocket)
    ws.state = state
    ws.speak = AsyncMock()
    return ws, decryptor


def test_reconnect_key_reaches_reader():
    old_key, new_key = nacl.utils.random(32), nacl.utils.random(32)
    ws, decryptor = _ws_with_reader(old_key)

    asyncio.run(ws.load_secret_key({"secret_key": list(new_key)}))

    nonce = nacl.utils.random(24)
    packet = nacl.secret.Aead(new_key).encrypt(b"audio", nonce=nonce).ciphertext
    assert decryptor.box.decrypt(packet, nonce=nonce) == b"audio"


def test_no_reader_is_fine():
    ws, _ = _ws_with_reader(nacl.utils.random(32))
    ws.state.client._reader = None
    asyncio.run(ws.load_secret_key({"secret_key": list(nacl.utils.random(32))}))
