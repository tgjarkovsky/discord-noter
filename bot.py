import asyncio
import logging
from datetime import datetime
from pathlib import Path

import discord
from discord.voice import VoiceClient

from config import load_settings
from recorder import TimedWaveSink
from transcriber import load_model, transcribe_recording, format_transcript
from notes_generator import generate_notes
from projects import list_projects, style_folder
from output_files import output_base, write_notes, write_transcript
from voice_alerts import ChatAlertHandler, outages

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

settings = load_settings()

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)


@bot.event
async def on_ready():
    await bot.sync_commands()
    log.info(f"Bot přihlášen jako {bot.user}, příkazy synchronizovány.")


log.info(f"Načítám Whisper model '{settings.whisper_model}'...")
whisper_model = load_model(settings.whisper_model, settings.whisper_device)
log.info("Whisper připraven.")

# guild_id -> voice_client; None = slot rezervován / probíhá zastavování
active_sessions: dict[int, VoiceClient | None] = {}

# guild_id -> ID toho, kdo zavolal /note-stop (None = automatické zastavení)
pending_stop: dict[int, int | None] = {}

# guild_id -> (textový kanál pro upozornění, sink) běžícího nahrávání
recordings: dict[int, tuple[discord.abc.Messageable, TimedWaveSink]] = {}


# ponytail: log py-cordu neříká guild, problém se hlásí všem běžícím nahrávkám
def _send_alert(text: str) -> None:
    for channel, _ in list(recordings.values()):
        asyncio.run_coroutine_threadsafe(channel.send(text), bot.loop)


def _mark_issue(kind: str) -> None:
    for _, sink in list(recordings.values()):
        sink.mark(kind)


logging.getLogger("discord").addHandler(ChatAlertHandler(_send_alert, _mark_issue))

SKIP = "__skip__"


@bot.check
async def _is_allowed(ctx: discord.ApplicationContext) -> bool:
    """Prázdný whitelist = bez omezení."""
    return not settings.allowed_user_ids or ctx.author.id in settings.allowed_user_ids


@bot.event
async def on_application_command_error(ctx: discord.ApplicationContext, error: discord.DiscordException):
    if isinstance(error, discord.CheckFailure):
        await ctx.respond("Nemáš oprávnění používat tento příkaz.", ephemeral=True)
        return
    log.error(f"Příkaz /{ctx.command} selhal: {error}", exc_info=error)
    try:
        await ctx.respond("Příkaz selhal, detail je v logu bota.", ephemeral=True)
    except discord.DiscordException:
        pass


# ── Recording ─────────────────────────────────────────────────────────────────

@bot.slash_command(name="note-start", description="Bot se připojí do tvého voice kanálu a začne nahrávat.")
async def join(ctx: discord.ApplicationContext):
    if not ctx.author.voice:
        await ctx.respond("Nejsi ve voice kanálu.", ephemeral=True)
        return
    if ctx.guild_id in active_sessions:
        await ctx.respond("Nahrávání už probíhá.", ephemeral=True)
        return
    # Bez oprávnění py-cord nevyhodí chybu, ale zasekne se na voice handshaku
    perms = ctx.author.voice.channel.permissions_for(ctx.guild.me)
    if not (perms.view_channel and perms.connect):
        await ctx.respond(
            f"Nemám oprávnění **Zobrazit kanál** a **Připojit** v **{ctx.author.voice.channel.name}**. "
            "Přidej je roli bota v nastavení kanálu nebo kategorie.",
            ephemeral=True,
        )
        return

    # Rezervuj slot před await, aby souběžné /note-start neprošlo kontrolou výše
    active_sessions[ctx.guild_id] = None
    try:
        # Připojení k voice trvá déle než 3 s limit Discordu na odpověď
        await ctx.defer()
        channel = ctx.author.voice.channel
        voice_client = await channel.connect()
    except Exception:
        active_sessions.pop(ctx.guild_id, None)
        raise

    sink = TimedWaveSink()
    voice_client.start_recording(sink, _recording_finished_callback, ctx.channel)

    active_sessions[ctx.guild_id] = voice_client
    recordings[ctx.guild_id] = (ctx.channel, sink)
    await ctx.respond(f"Připojeno do **{channel.name}** — nahrávám. Zastav pomocí `/note-stop`.")


def _stop_recording(guild_id: int, invoker_id: int | None) -> bool:
    voice_client = active_sessions.get(guild_id)
    if voice_client is None:
        return False
    active_sessions[guild_id] = None
    pending_stop[guild_id] = invoker_id
    voice_client.stop_recording()
    return True


@bot.slash_command(name="note-stop", description="Zastaví nahrávání a vygeneruje zápis.")
async def stop(ctx: discord.ApplicationContext):
    if not _stop_recording(ctx.guild_id, ctx.author.id):
        await ctx.respond("Žádné aktivní nahrávání.", ephemeral=True)
        return
    await ctx.respond("Zastavuji nahrávání, čekej...")


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    voice_client = active_sessions.get(member.guild.id)
    if voice_client is None or before.channel != voice_client.channel:
        return
    if any(not m.bot for m in voice_client.channel.members):
        return
    log.info(f"Kanál {voice_client.channel} je prázdný, zastavuji nahrávání.")
    _stop_recording(member.guild.id, None)


# ── Post-recording flow ───────────────────────────────────────────────────────

class ProjectSelectView(discord.ui.View):
    def __init__(self, projects: list[str], invoker_id: int | None):
        super().__init__(timeout=120)
        self.invoker_id = invoker_id
        self.chosen: str | None = None  # název projektu, SKIP, nebo None po timeoutu

        # ponytail: Discord select má max 25 možností, projekty nad 24 se nezobrazí
        options = [discord.SelectOption(label=name, value=name) for name in projects[:24]]
        options.append(discord.SelectOption(label="— Bez vzoru —", value=SKIP))

        select = discord.ui.Select(placeholder="Vyber projekt…", options=options)
        select.callback = self._on_select
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.invoker_id is None or interaction.user.id == self.invoker_id:
            return True
        await interaction.response.send_message("Projekt vybírá ten, kdo zastavil nahrávání.", ephemeral=True)
        return False

    async def _on_select(self, interaction: discord.Interaction):
        self.chosen = interaction.data["values"][0]
        await interaction.response.defer()
        self.stop()


async def _ask_project(channel: discord.TextChannel, invoker_id: int | None) -> str | None:
    projects = list_projects()
    if not projects:
        return None
    view = ProjectSelectView(projects, invoker_id)
    msg = await channel.send("Ke kterému projektu zápis patří? (přepis mezitím běží)", view=view)
    await view.wait()
    await msg.delete()
    if view.chosen is None:
        await channel.send("Projekt nevybrán včas — zápis bude ve výchozím stylu.")
        return None
    return None if view.chosen == SKIP else view.chosen


async def _recording_finished_callback(sink: TimedWaveSink, channel: discord.TextChannel, *args):
    guild = channel.guild
    invoker_id = pending_stop.pop(guild.id, None)
    active_sessions.pop(guild.id, None)
    recordings.pop(guild.id, None)

    try:
        await sink.vc.disconnect()
        if invoker_id is None:
            await channel.send("Všichni opustili voice kanál — nahrávání ukončeno.")
        await channel.send("Přepisuji audio (může to chvíli trvat)...")

        loop = asyncio.get_running_loop()
        transcription = loop.run_in_executor(None, transcribe_recording, sink, whisper_model)
        project_name = await _ask_project(channel, invoker_id)
        segments = await transcription

        if not segments:
            await channel.send("Nepodařilo se přepsat žádné audio. Zápis nebyl vytvořen.")
            return

        transcript = format_transcript(segments, outages(sink.marks))

        base = output_base(settings.notes_output_dir, project_name, datetime.now())
        transcript_path = write_transcript(base, transcript)

        await channel.send("Generuji zápis pomocí Claude...")
        meeting_date = sink.started_at.strftime("%Y-%m-%d %H:%M")
        try:
            notes_md = await loop.run_in_executor(
                None,
                generate_notes,
                transcript,
                meeting_date,
                style_folder(project_name) if project_name else None,
                settings.anthropic_api_key,
                settings.claude_model,
            )
        except Exception as e:
            log.error(f"Chyba generate_notes: {e}", exc_info=True)
            await channel.send(
                f"Zápis se nepodařilo vygenerovat ({type(e).__name__}). Přepis je uložen v `{transcript_path}`.",
                file=discord.File(transcript_path),
            )
            return

        notes_path = write_notes(base, notes_md)

        header = f"**Zápis uložen:** `{notes_path}`"
        await channel.send(header, files=[discord.File(notes_path), discord.File(transcript_path)])

    except Exception as e:
        log.error(f"Chyba v _recording_finished_callback: {e}", exc_info=True)
        try:
            await channel.send(f"Při zpracování záznamu nastala chyba ({type(e).__name__}). Detail je v logu.")
        except Exception:
            pass


bot.run(settings.discord_token)
