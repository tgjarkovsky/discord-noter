## [2026-10-27] - Datum porady v zápisu je čas začátku nahrávání

- `TimedWaveSink.started_at` uloží čas startu nahrávky; `bot.py` ho dává Claude jako datum porady místo času dokončení přepisu.
## [2026-10-27] - README: oprávnění bota a WHISPER_DEVICE

- Doplněna oprávnění `View Channels` a `Attach Files`, opravena věta o GPU (výchozí je CPU), do `.env` přidán `WHISPER_DEVICE`.
## [2026-10-27] - Po pádu během nahrávání bot po startu ohlásí ztracenou poradu

- `session_state.py`: běžící nahrávání se zapisují do `<NOTES_OUTPUT_DIR>/.active_recordings.json`. Po startu bot do příslušných kanálů napíše, že nahrávání bylo přerušeno. README doplněno o autostart (systemd, Plánovač úloh).

## [2026-10-27] - Přepis se ukládá před voláním Claude

- `output_files.py`: zápis souborů výstupu. Přepis se uloží na disk hned po přepisu; když Claude API selže, bot to napíše do kanálu a přiloží přepis.

## [2026-10-27] - Přidán ROADMAP.md

- Vize, uživatelé, směry na 1–3 měsíce (nasazení pro self-host týmy, spolehlivost nahrávání, výstupy) a co nedělat (bez SaaS, bez plně cloudového řešení).

## [2026-10-20] - Odstraněn Google Drive, projekty ze složky styles/

- Pryč upload na Drive, `/project` příkazy a Google závislosti. Projekt = podsložka `styles/` se vzorovými zápisy (mimo git).

## [2026-10-20] - Upozornění na problémy s voice do chatu

- `voice_alerts.py`: výpadek voice spojení a opakované chyby dešifrování/dekódování audia bot napíše do kanálu, kde padlo `/note-start` (stejná zpráva max 1× za 60 s).
- Výpadky audia (spadlé spojení, nedešifrovatelné/nedekódovatelné audio) se vyznačí v přepisu s časovým úsekem a Claude je uvede nahoře v zápisu.

## [2026-10-20] - Oprava ztráty audia po reconnectu voice spojení

- Po reconnectu voice websocketu (např. close 1006) py-cord nepředal nový `secret_key` AudioReaderu → zbytek nahrávky `CryptoError: Decryption failed`. Patch `VoiceWebSocket.load_secret_key` v `recorder.py` klíč předá.

## [2026-09-24] - Voice s DAVE E2EE, oprava přepisu na CPU, logování tokenů

- py-cord z PR #3159 (DAVE receive), připnuto na commit — vydaný py-cord s DAVE nenahrává
- `TimedWaveSink` (`recorder.py`) doplňuje ticho podle reálného času — nový py-cord to nedělá
- `/note-start`: `ctx.defer()` (fix „Aplikace neodpovídá"), kontrola oprávnění View/Connect předem (jinak tichý hang)
- Whisper defaultně na CPU (`WHISPER_DEVICE`), `auto` padal na chybějícím cuBLAS
- Log spotřeby Claude tokenů (vstup/výstup) po každém zápisu

## [2026-09-24] - faster-whisper turbo, zjednodušený flow po nahrávání

- Whisper → `faster-whisper` (`large-v3-turbo`, int8, VAD); odpadá torch/openai-whisper a pydub
- Oprava: WAV konstanty `WaveSink.AUDIO_*` v py-cord 2.7 neexistují → přepis padal; nyní `discord.opus.Decoder`
- Časování stop přes `sync_start=True`; smazán `recorder.py` (vlastní offsety)
- Složka se vzory je volitelná vlastnost projektu (`/project add ... style_folder`); zrušen dotaz v chatu → není potřeba Message Content Intent
- Projekt se vybírá hned po zastavení (paralelně s přepisem), jen autor `/note-stop`, timeout 2 min s hláškou
- Zápis + přepis ukládány lokálně a posílány jako přílohy; název souboru obsahuje projekt
- Auto-stop nahrávání, když voice kanál opustí všichni lidé
- Autocomplete v `/project remove`, globální kontrola oprávnění (`@bot.check`)
- `CLAUDE_MODEL` v env, `max_tokens` 8192 + upozornění na zkrácený zápis
- Srozumitelná chyba při chybějící povinné env proměnné
- Tray: bot startuje automaticky, položka „Otevřít log", kill fallback, log handle už neleakuje
- `bot.log` v `.gitignore`, `ALLOWED_USER_IDS` a `CLAUDE_MODEL` v `.env.example`

## [2026-03-25] - Security & reliability fixes

- Přidána autorizace přes `ALLOWED_USER_IDS` env var (všechny slash příkazy)
- `msg_check` v callbacku nyní přijímá odpověď jen od toho, kdo zavolal `/stop`
- Validace cesty ke složce vzorových zápisů (musí být existující adresář)
- Race condition na `/join` — slot se rezervuje před `await channel.connect()`
- `asyncio.get_event_loop()` → `get_running_loop()` (Python 3.12+ kompatibilita)
- Top-level `try/except` v `_recording_finished_callback` — chyby se reportují do kanálu
- Discord zpráva s preview nepřekročí 2000 znaků
- Drive upload error — detail do logu, generická zpráva do Discordu
- Drive upload odstraněn automatický `anyone/reader` permission

## [2026-03-25] - Přidány testy

48 testů pro `projects.py`, `transcriber.py`, `notes_generator.py`. Pytest konfigurace v `pytest.ini`.
