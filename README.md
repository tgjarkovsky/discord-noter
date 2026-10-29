# Discord Voice Noter

Bot nahrává hlasové hovory na Discordu, přepíše je pomocí Whisper a vygeneruje strukturovaný zápis z porady pomocí Claude.

---

## Požadavky

- Python 3.11+
- Whisper běží lokálně přes `faster-whisper` (výchozí je CPU, GPU zapneš přes `WHISPER_DEVICE=cuda`, pokud máš nainstalované CUDA knihovny)
- Discord bot token
- Anthropic API klíč

---

## Instalace

```bash
pip install -r requirements.txt
```

Vytvoř `.env` soubor (viz sekce Konfigurace).

---

## Konfigurace

Soubor `.env` v kořeni projektu:

```env
# Povinné
DISCORD_TOKEN=tvůj_discord_bot_token
ANTHROPIC_API_KEY=tvůj_anthropic_klíč

# Kdo může používat bota (čárkou oddělená Discord User ID)
# Prázdné = kdokoliv na serveru
ALLOWED_USER_IDS=123456789012345678

# Volitelné
WHISPER_MODEL=large-v3-turbo    # výchozí: large-v3-turbo
CLAUDE_MODEL=claude-sonnet-4-6  # model pro generování zápisu
NOTES_OUTPUT_DIR=./notes        # kam se ukládají zápisy lokálně
WHISPER_DEVICE=cpu              # výchozí: cpu; cuda jen s nainstalovanými CUDA knihovnami (cuBLAS/cuDNN)
```

### Jak zjistit Discord User ID

V Discordu: Nastavení → Pokročilé → zapnout **Vývojářský režim** → pravý klik na sebe → **Kopírovat ID uživatele**.

### Pozvání bota na server

1. Jdi na [discord.com/developers](https://discord.com/developers/applications) → vyber svou aplikaci
2. Vlevo **OAuth2 → URL Generator**
3. Zaškrtni Scopes: `bot` + `applications.commands`
4. Zaškrtni Bot Permissions: `View Channels`, `Send Messages`, `Attach Files`, `Connect`, `Speak`, `Use Voice Activity`
5. Zkopíruj vygenerovanou URL → otevři v prohlížeči → vyber server → Autorizovat

### Potřebné intenty

Žádné privilegované intenty nejsou potřeba.

---

## Spuštění

```bash
python bot.py
```

Nebo přes tray ikonu (Windows): spusť `start_bot.vbs` nebo `tray.py` — bot se spustí automaticky a běží na pozadí s ikonou v systémové liště. Výstup jde do `bot.log` (v menu **Otevřít log**).

### Autostart a restart po pádu

Když bot spadne během nahrávání, audio je ztracené. Po novém startu to ohlásí do kanálu, kde se nahrávání spustilo. Aby naskočil sám, spouštěj ho pod správcem procesů.

**Linux (systemd)**: zkopíruj `deploy/discord-noter.service` do `/etc/systemd/system/`, uprav cesty a zapni: `sudo systemctl enable --now discord-noter`. Unit má `Restart=on-failure` a `PYTHONUTF8=1`.

**Windows (tray)**: dej zástupce na `start_bot.vbs` do složky Po spuštění (`Win+R` → `shell:startup`). Tray bota po pádu sám spustí znovu (po 5 s, 30 s, 2 min). Po 5 restartech za 10 minut (šestý pád) to vzdá, ikona zešedne a důvod je v `bot.log`. Ruční zastavení přes menu restart nespustí.

**Windows (Plánovač úloh)**: úloha se spouštěčem „Při přihlášení“, akce `wscript start_bot.vbs` s pracovní složkou ve složce bota.

> **Poznámka:** Při prvním spuštění se stahuje Whisper model (~1,6 GB pro `large-v3-turbo`). Bot se připojí k Discordu až po načtení modelu.

---

## Příkazy

### Nahrávání

| Příkaz | Popis |
|--------|-------|
| `/note-start` | Bot se připojí do tvého aktuálního voice kanálu a začne nahrávat |
| `/note-stop` | Zastaví nahrávání a spustí zpracování |
| `/note-regenerate` | Vygeneruje nový zápis z uloženého přepisu (volitelně s jiným projektem), původní zápis přepíše |

Nahrávání se zastaví i samo, když z voice kanálu odejdou všichni lidé.

---

## Typický průběh

1. Přijdi do voice kanálu s ostatními
2. Napiš `/note-start` v textovém kanálu — bot se připojí a začne nahrávat
3. Po skončení porady napiš `/note-stop` (nebo prostě všichni odejděte)
4. Pokud existují projekty (viz níže), vyber ze seznamu, ke kterému zápis patří (nebo „Bez vzoru“) — přepis mezitím běží na pozadí. Vybírat může jen ten, kdo nahrávání zastavil; po 2 minutách se pokračuje ve výchozím stylu.
5. Probíhá přepis (Whisper) a generování zápisu (Claude)
6. Bot pošle do kanálu zápis a přepis jako přílohy `.md`

### Projekty a vzorové zápisy (styl)

Projekt = podsložka `styles/` s existujícími `.md` zápisy. Bot přečte posledních 5 souborů a použije je jako ukázku stylu pro Claude.

```
styles/
  Tym/
    2026-03-18.md
    2026-03-25.md
```

Složka `styles/` není v gitu (obsahuje skutečné zápisy z porad). Nový projekt nebo vzor = přidat soubory do `styles/` a restartovat bota.

---

## Uložené soubory

Zápisy se ukládají do `NOTES_OUTPUT_DIR` (výchozí: `./notes/`) ve formátu:

```
notes/
  2026-03-25_14-30_Tym.md          # zápis
  2026-03-25_14-30_Tym_prepis.md   # přepis s časy a mluvčími
  ...
```

---

## Whisper modely

| Model | Velikost | Rychlost | Přesnost |
|-------|----------|----------|----------|
| `tiny` | ~75 MB | nejrychlejší | nízká |
| `base` | ~150 MB | rychlý | dobrá |
| `small` | ~500 MB | střední | dobrá |
| `medium` | ~1.5 GB | pomalý | velmi dobrá |
| `large-v3-turbo` | ~1.6 GB | střední | velmi dobrá (výchozí) |
| `large-v3` | ~3 GB | nejpomalejší | nejlepší |

Nastav v `.env`: `WHISPER_MODEL=medium`
