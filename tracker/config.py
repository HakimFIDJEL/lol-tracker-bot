"""Validation de la configuration avant connexion."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    discord_token: str
    riot_api_key: str
    game_name: str
    tag_line: str
    channel_id: int
    user_to_ping: int | None
    environment: str
    state_dir: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        values = os.environ if env is None else env

        def required(name: str) -> str:
            value = values.get(name, "").strip()
            if not value:
                raise ValueError(f"Variable obligatoire absente : {name}")
            return value

        environment = values.get("ENVIRONMENT", "testing")
        if environment not in {"testing", "production"}:
            raise ValueError("ENVIRONMENT doit être testing ou production")
        channel_id = int(required("DISCORD_CHANNEL_ID"))
        ping = values.get("DISCORD_USER_TO_PING_ID", "").strip()
        user_to_ping = int(ping) if ping else None
        if channel_id <= 0 or (user_to_ping is not None and user_to_ping <= 0):
            raise ValueError("Les identifiants Discord doivent être positifs")
        return cls(
            discord_token=required("DISCORD_TOKEN"),
            riot_api_key=required("RIOT_API_KEY"),
            game_name=required("USER_GAMENAME"),
            tag_line=required("USER_TAGLINE"),
            channel_id=channel_id,
            user_to_ping=user_to_ping,
            environment=environment,
            state_dir=Path(values.get("STATE_DIR", "/data")),
        )
