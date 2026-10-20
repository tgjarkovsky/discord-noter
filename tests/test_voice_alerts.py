import logging
from unittest.mock import patch

from voice_alerts import COOLDOWN, MIN_AUDIO_ERRORS, ChatAlertHandler, Outage, outages

DISCONNECT = "Disconnected from voice... Reconnecting in 0.15s"
CRYPTO = "CryptoError while decoding a voice packet"
OPUS = "Opus decode failed for packet seq=%s, using PLC"


def _handler():
    sent = []
    logger = logging.getLogger("test_voice_alerts")
    logger.propagate = False
    logger.handlers = [ChatAlertHandler(sent.append)]
    return logger, sent


def _log_at(logger, times, msg, *args):
    with patch("voice_alerts.time.monotonic", side_effect=list(times)):
        for _ in times:
            logger.error(msg, *args)


def test_disconnect_alerts_immediately():
    logger, sent = _handler()
    _log_at(logger, [0.0], DISCONNECT)
    assert len(sent) == 1 and "spadlo" in sent[0]


def test_flood_sends_single_alert():
    logger, sent = _handler()
    _log_at(logger, [i * 0.02 for i in range(100)], CRYPTO)
    assert len(sent) == 1 and "dešifrovat" in sent[0]


def test_few_audio_errors_are_ignored():
    # Pár vadných paketů při přechodu na DAVE je běžné a audio se dopočítá (PLC)
    logger, sent = _handler()
    _log_at(logger, [0.0, 0.01, 0.02], OPUS, 1)
    assert sent == []


def test_alert_repeats_after_cooldown():
    logger, sent = _handler()
    _log_at(logger, [0.0, COOLDOWN + 1], DISCONNECT)
    assert len(sent) == 2


def test_unrelated_log_ignored():
    logger, sent = _handler()
    _log_at(logger, [0.0], "Upgrading to DAVE connection for channel 1")
    assert sent == []


def test_handler_marks_every_issue():
    marks = []
    logger = logging.getLogger("test_voice_alerts_marks")
    logger.propagate = False
    logger.handlers = [ChatAlertHandler(lambda _: None, marks.append)]
    for msg in [DISCONNECT, "Voice connection completed", CRYPTO, "Upgrading to DAVE"]:
        logger.error(msg)
    assert marks == ["disconnect", "reconnected", "crypto"]


class TestOutages:
    def test_disconnect_until_reconnected(self):
        assert outages([(10.0, "disconnect"), (16.0, "reconnected")]) == [Outage(10.0, 16.0, "spojení spadlo")]

    def test_disconnect_without_reconnect_is_open(self):
        assert outages([(10.0, "disconnect")]) == [Outage(10.0, None, "spojení spadlo")]

    def test_error_burst_merges_into_one_outage(self):
        marks = [(100 + i * 0.02, "crypto") for i in range(MIN_AUDIO_ERRORS)]
        assert outages(marks) == [Outage(100.0, marks[-1][0], "audio nešlo dešifrovat")]

    def test_few_errors_are_noise(self):
        assert outages([(5.0, "opus"), (5.1, "opus"), (5.2, "opus")]) == []

    def test_gap_splits_bursts(self):
        first = [(i * 0.02, "opus") for i in range(MIN_AUDIO_ERRORS)]
        second = [(100 + i * 0.02, "opus") for i in range(MIN_AUDIO_ERRORS)]
        result = outages(second + first)  # pořadí vstupu nehraje roli
        assert [o.start for o in result] == [0.0, 100.0]
        assert all(o.reason == "audio nešlo dekódovat" for o in result)
