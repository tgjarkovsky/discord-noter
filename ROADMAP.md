# Roadmap

Aktualizováno 2026-10-27. Horizont: listopad 2026 až leden 2027.

## Vize

Discord bot, který z hlasové porady udělá zápis a přepis bez ruční práce. Každý tým si ho provozuje sám: přepis běží lokálně (faster-whisper), do cloudu jde jen text pro Claude.

Cíl na příští 1–3 měsíce: cizí tým si bota rozjede z veřejného repa bez pomoci autora a nahrávání nepřichází o audio.

## Uživatelé

- Malé týmy (2–10 lidí), které se scházejí ve voice kanálu na Discordu a chtějí zápis s rozhodnutími a úkoly.
- Bota si hostují samy. Správce je jeden technicky zdatný člověk z týmu: zvládne Python a `.env`, ale vnitřek bota nezná a nechce ho číst.
- Dnes bot používá autorův tým na Windows přes tray (`tray.py`). Další týmy zatím nejsou, roadmapa je má umožnit.

## Směry

### 1. Nasazení a provoz pro cizí tým

Platforma pro self-host (Docker, nativní Linux, Windows) není rozhodnutá. Kroky musí fungovat nezávisle na ní.

1. **Quickstart do prvního zápisu za 15 minut.** README vede od klonu repa k prvnímu zápisu. Kontrola konfigurace při startu: platný Discord token, funkční Anthropic klíč, stažený Whisper model. Chyby vypisovat česky a s tím, co opravit, ne jako traceback. Hotovo, když to nový člověk projde podle README bez dotazu.
2. **Restart po pádu a autostart.** Bot se po pádu sám zvedne. Návod pro systemd a pro Windows (Task Scheduler nebo tray). Když spadl během nahrávání, po startu to napíše do kanálu.
3. **Bezpečný update.** py-cord je připnutý na commit z PR #3159 (DAVE receive) a `recorder.py` patchuje `VoiceWebSocket.load_secret_key`. Popsat postup updatu a přidat smoke test, který po updatu ověří, že patch pořád sedí. Až vyjde py-cord s DAVE receive, přejít na vydanou verzi a patch zrušit, pokud už není potřeba.

### 2. Spolehlivost nahrávání

1. **Audio průběžně na disk.** Celé nahrávání je teď v paměti (`TimedWaveSink`). Pád procesu znamená ztracenou poradu. Zapisovat stopy průběžně do souborů a po restartu nedokončené nahrávání zpracovat.
2. **Neztrácet mezivýsledky.** Přepis se ukládá až po úspěšném zápisu z Claude, takže chyba API zahodí i hotový přepis. Uložit přepis hned po Whisperu a umožnit vygenerovat zápis znovu z uloženého přepisu.
3. **Delší výpadky voice.** Krátký reconnect už audio neztrácí (oprava 2026-10-20). Ověřit výpadek v řádu minut a přesun voice serveru. Pokud nahrávání skončí, bot to musí říct do kanálu a nabídnout pokračování.
4. **Dlouhé porady.** Ověřit poradu delší než 2 hodiny: paměť, doba přepisu na CPU, limit `max_tokens` 8192 u zápisu.

### 3. Výstup a kvalita zápisů (nízká priorita)

1. **Zápis jako vlákno v Discordu.** Po zpracování založit vlákno, v něm shrnutí a akční body jako text. Přílohy `.md` zůstávají.
2. **Akční body s vlastníkem a termínem.** Úprava promptu v `notes_generator.py`, bez nových závislostí.
3. **Návaznost na minulou poradu.** Otevřené úkoly z posledního zápisu téhož projektu převzít do nového zápisu.
4. **Volitelný cloudový přepis.** Pro týmy se slabým hardwarem. Lokální Whisper zůstává výchozí, cloud STT jen jako explicitní volba v `.env`.

## Co ne

- **Hostovaná instance pro cizí servery.** Žádný SaaS ani multi-tenant provoz. Každý tým běží u sebe se svými klíči.
- **Plně cloudové řešení.** Lokální přepis zůstává výchozí a audio ve výchozím nastavení neopouští stroj.
