"""System tray launcher pro discord-noter."""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from PIL import Image, ImageDraw
import pystray

BOT_SCRIPT = Path(__file__).parent / "bot.py"
PYTHON = sys.executable

_process: subprocess.Popen | None = None
_icon: pystray.Icon | None = None
_stopped_by_user = False
_gave_up = False

RESTART_DELAYS = (5.0, 30.0, 120.0)
MAX_CRASHES = 5
CRASH_WINDOW = 600.0


# ── Ikony ─────────────────────────────────────────────────────────────────────

def _make_icon(running: bool) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = (88, 101, 242) if running else (128, 132, 142)  # Discord blue / šedá
    draw.ellipse([8, 8, 56, 56], fill=color)
    # Malý zelený/červený indikátor
    dot = (87, 242, 135) if running else (237, 66, 69)
    draw.ellipse([38, 38, 56, 56], fill=dot)
    return img


# ── Bot process ───────────────────────────────────────────────────────────────

def _is_running() -> bool:
    return _process is not None and _process.poll() is None


def restart_delay(crash_times: list[float], now: float) -> float | None:
    """Pauza před dalším restartem podle pádů v posledních 10 minutách; None = vzdát to."""
    recent = [t for t in crash_times if now - t < CRASH_WINDOW]
    if len(recent) > MAX_CRASHES:
        return None
    return RESTART_DELAYS[min(len(recent), len(RESTART_DELAYS)) - 1]


LOG_FILE = Path(__file__).parent / "bot.log"


def _log(message: str):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[tray] {message}\n")


def _start(_icon, _item=None, auto=False):
    global _process, _stopped_by_user, _gave_up
    if _is_running():
        return
    if not auto:
        _stopped_by_user = False
        _gave_up = False
    # Proces dědí handle, rodič si svou kopii může hned zavřít
    with open(LOG_FILE, "a", encoding="utf-8") as log_out:
        _process = subprocess.Popen(
            [PYTHON, str(BOT_SCRIPT)],
            cwd=BOT_SCRIPT.parent,
            stdout=log_out,
            stderr=log_out,
        )
    _refresh()


def _stop(_icon, _item=None):
    global _process, _stopped_by_user
    _stopped_by_user = True
    if _process and _is_running():
        _process.terminate()
        try:
            _process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _process.kill()
    _process = None
    _refresh()


def _open_log(_icon, _item=None):
    LOG_FILE.touch()
    os.startfile(LOG_FILE)


def _restart(_icon, _item=None):
    _stop(_icon)
    _start(_icon)


def _exit(_icon, _item=None):
    _stop(_icon)
    _icon.stop()


# ── Tray menu ─────────────────────────────────────────────────────────────────

def _menu() -> pystray.Menu:
    return pystray.Menu(
        pystray.MenuItem(
            lambda _: "● Bot běží" if _is_running() else "○ Bot zastaven",
            None,
            enabled=False,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Spustit", _start, enabled=lambda _: not _is_running()),
        pystray.MenuItem("Zastavit", _stop, enabled=lambda _: _is_running()),
        pystray.MenuItem("Restartovat", _restart, enabled=lambda _: _is_running()),
        pystray.MenuItem("Otevřít log", _open_log),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Ukončit", _exit),
    )


def _refresh():
    if _icon:
        _icon.icon = _make_icon(_is_running())
        if _is_running():
            _icon.title = "discord-noter — běží"
        elif _gave_up:
            _icon.title = "discord-noter — spadl, restart vypnut (viz bot.log)"
        else:
            _icon.title = "discord-noter — zastaven"


# ── Watchdog — aktualizuje ikonu pokud bot spadne ─────────────────────────────

def _watchdog():
    global _gave_up
    last = None
    crash_times: list[float] = []
    restart_at: float | None = None
    while True:
        now = _is_running()
        if now != last:
            _refresh()
            last = now
        t = time.monotonic()
        if not now and not _stopped_by_user and not _gave_up:
            if restart_at is None:
                crash_times.append(t)
                delay = restart_delay(crash_times, t)
                if delay is None:
                    _gave_up = True
                    _log(f"Bot spadl víc než {MAX_CRASHES}× za {CRASH_WINDOW // 60:.0f} min, automatický restart vypnut.")
                    _refresh()
                else:
                    _log(f"Bot spadl, restart za {delay:.0f} s.")
                    restart_at = t + delay
            elif t >= restart_at:
                restart_at = None
                _start(_icon, auto=True)
        else:
            restart_at = None
        time.sleep(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global _icon
    _icon = pystray.Icon(
        name="discord-noter",
        icon=_make_icon(False),
        title="discord-noter — zastaven",
        menu=_menu(),
    )
    _start(_icon)
    threading.Thread(target=_watchdog, daemon=True).start()
    _icon.run()


if __name__ == "__main__":
    main()
