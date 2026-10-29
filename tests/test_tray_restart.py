import tray


def test_first_crash_short_delay():
    assert tray.restart_delay([100.0], 100.0) == 5.0


def test_delay_grows_with_crashes():
    delays = [tray.restart_delay([100.0 + i for i in range(n)], 100.0 + n - 1) for n in (1, 2, 3, 5)]
    assert delays == [5.0, 30.0, 120.0, 120.0]


def test_sixth_crash_within_window_stops():
    crashes = [0.0, 60.0, 120.0, 180.0, 240.0, 300.0]
    assert tray.restart_delay(crashes, 300.0) is None


def test_old_crashes_are_forgotten():
    crashes = [0.0, 1.0, 2.0, 3.0, 4.0, 700.0]
    assert tray.restart_delay(crashes, 700.0) == 5.0
