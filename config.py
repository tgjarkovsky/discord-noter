from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass
class Settings:
    discord_token: str
    anthropic_api_key: str
    whisper_model: str
    whisper_device: str
    claude_model: str | None
    notes_output_dir: str
    allowed_user_ids: list[int]  # empty = no restriction


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Chybí povinná proměnná {name} v .env (viz .env.example).")
    return value


def load_settings() -> Settings:
    raw_ids = os.environ.get("ALLOWED_USER_IDS", "")
    allowed_user_ids = [int(x.strip()) for x in raw_ids.split(",") if x.strip().isdigit()]
    return Settings(
        discord_token=_require("DISCORD_TOKEN"),
        anthropic_api_key=_require("ANTHROPIC_API_KEY"),
        whisper_model=os.environ.get("WHISPER_MODEL", "large-v3-turbo"),
        whisper_device=os.environ.get("WHISPER_DEVICE", "cpu"),
        claude_model=os.environ.get("CLAUDE_MODEL") or None,
        notes_output_dir=os.environ.get("NOTES_OUTPUT_DIR", "./notes"),
        allowed_user_ids=allowed_user_ids,
    )
