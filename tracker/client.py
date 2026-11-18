"""Surveillance, publication et gestion des erreurs temporaires."""

import asyncio
import logging
import os
import time
from pathlib import Path

import aiohttp
import discord
from discord.ext import tasks

from tracker.config import Settings
from tracker.riot import MatchReport, RiotClient
from tracker.state import StateStore

LOGGER = logging.getLogger(__name__)
HEARTBEAT = Path("/tmp/lol-tracker-heartbeat")


def embed_report(report: MatchReport) -> discord.Embed:
    embed = discord.Embed(
        title="Victoire !" if report.win else "Défaite !",
        color=0x2ECC71 if report.win else 0xE74C3C,
    )
    for name, value in (
        ("Champion joué", report.champion),
        ("Mode de jeu", report.mode),
        ("Poste", report.lane),
        ("Score", f"**{report.score}/100**"),
        ("KDA", f"{report.kills}/{report.deaths}/{report.assists}"),
        ("Durée", f"{report.duration} min"),
    ):
        embed.add_field(name=name, value=value, inline=True)
    if not report.win:
        embed.add_field(name="FF ?", value="Oui" if report.surrender else "Non", inline=True)
    embed.set_footer(text=f"Fin : {report.ended_at}")
    return embed


class TrackerClient(discord.Client):
    def __init__(self, settings: Settings) -> None:
        super().__init__(intents=discord.Intents.default())
        self.settings = settings
        self.state: StateStore | None = None
        self.session: aiohttp.ClientSession | None = None
        self.riot: RiotClient | None = None
        self.puuid: str | None = None

    async def setup_hook(self) -> None:
        identity = f"{self.settings.game_name}#{self.settings.tag_line}:{self.settings.environment}:{self.settings.channel_id}"
        self.state = StateStore(self.settings.state_dir, identity)
        self.session = aiohttp.ClientSession(
            headers={"X-Riot-Token": self.settings.riot_api_key},
            timeout=aiohttp.ClientTimeout(total=15),
        )
        self.riot = RiotClient(self.session)
        self.monitor.start()

    async def close(self) -> None:
        self.monitor.cancel()
        task = self.monitor.get_task()
        if task is not None:
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self.session is not None:
            await self.session.close()
        if self.state is not None:
            self.state.close()
        await super().close()

    async def poll(self) -> None:
        if self.riot is None or self.state is None:
            raise RuntimeError("Bot non initialisé")
        if self.puuid is None:
            self.puuid = await self.riot.puuid(self.settings.game_name, self.settings.tag_line)
        match_id = await self.riot.latest_match(self.puuid)
        if match_id is None or match_id == self.state.last_match():
            return
        report = await self.riot.report(match_id, self.puuid)
        if self.settings.environment == "testing":
            LOGGER.info("Simulation : nouveau match %s, aucun message envoyé", match_id)
        else:
            channel = self.get_channel(self.settings.channel_id)
            if channel is None:
                channel = await self.fetch_channel(self.settings.channel_id)
            if not isinstance(channel, discord.abc.Messageable):
                raise ValueError("Le salon configuré ne permet pas l'envoi de messages")
            content = f"<@{self.settings.user_to_ping}>" if self.settings.user_to_ping else None
            await channel.send(content=content, embed=embed_report(report))
            LOGGER.info("Match %s envoyé", match_id)
        # Un échec Discord ne doit pas marquer le match comme envoyé.
        self.state.save(match_id)

    @tasks.loop(minutes=1)
    async def monitor(self) -> None:
        if not self.is_ready():
            return
        try:
            await self.poll()
        except aiohttp.ClientResponseError as error:
            LOGGER.error(
                "Riot refuse la requête (HTTP %s), nouvel essai au prochain cycle", error.status
            )
        except (aiohttp.ClientError, TimeoutError, discord.HTTPException) as error:
            LOGGER.warning("Service temporairement indisponible (%s)", type(error).__name__)
        except (ValueError, KeyError) as error:
            LOGGER.error("Réponse ou configuration invalide (%s)", type(error).__name__)
        else:
            HEARTBEAT.write_text(str(time.time()))

    @monitor.before_loop
    async def before_monitor(self) -> None:
        await self.wait_until_ready()

    @monitor.error
    async def monitor_error(self, error: BaseException) -> None:
        LOGGER.error("Arrêt inattendu de la surveillance", exc_info=error)
        os._exit(1)
