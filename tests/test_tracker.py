import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import discord

from tracker.client import TrackerClient
from tracker.config import Settings
from tracker.riot import MatchReport, RiotClient, generate_score
from tracker.state import StateStore

ENV = {
    "DISCORD_TOKEN": "fake",
    "RIOT_API_KEY": "fake",
    "USER_GAMENAME": "Player",
    "USER_TAGLINE": "EUW",
    "DISCORD_CHANNEL_ID": "123",
    "ENVIRONMENT": "production",
}
REPORT = MatchReport(
    "Ahri", "Solo / Duo", "Midlane", True, 75, 8, 2, 6, 30, "01/01/2026 12:00", False
)


class ConfigTests(unittest.TestCase):
    def test_missing_token_fails_before_connection(self) -> None:
        with self.assertRaisesRegex(ValueError, "DISCORD_TOKEN"):
            Settings.from_env({**ENV, "DISCORD_TOKEN": ""})

    def test_invalid_environment_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "ENVIRONMENT"):
            Settings.from_env({**ENV, "ENVIRONMENT": "prod"})

    def test_testing_by_default(self) -> None:
        env = {key: value for key, value in ENV.items() if key != "ENVIRONMENT"}
        self.assertEqual(Settings.from_env(env).environment, "testing")


class StateTests(unittest.TestCase):
    def test_restart_preserves_match_and_second_instance_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            first = StateStore(path, "player")
            try:
                first.save("EUW_1")
                with self.assertRaises(RuntimeError):
                    StateStore(path, "player")
            finally:
                first.close()
            second = StateStore(path, "player")
            try:
                self.assertEqual(second.last_match(), "EUW_1")
            finally:
                second.close()

    def test_different_identity_does_not_reuse_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = StateStore(Path(directory), "testing")
            first.save("EUW_1")
            first.close()
            second = StateStore(Path(directory), "production")
            try:
                self.assertIsNone(second.last_match())
            finally:
                second.close()

    def test_invalid_state_is_not_silently_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory), "player")
            try:
                store.path.write_text("broken")
                with self.assertRaises(ValueError):
                    store.last_match()
            finally:
                store.close()


class ScoreTests(unittest.TestCase):
    def test_resources_use_actual_match_duration(self) -> None:
        player: dict[str, object] = {
            "kills": 0,
            "deaths": 1,
            "assists": 0,
            "totalMinionsKilled": 240,
            "individualPosition": "MIDDLE",
            "win": True,
        }
        self.assertEqual(generate_score(player, 1800), 40)
        self.assertEqual(generate_score(player, 3600), 25)


class PollTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.client = TrackerClient(Settings.from_env(ENV))
        self.client.state = StateStore(Path(self.directory.name), "player")
        self.riot = MagicMock(spec=RiotClient)
        self.riot.puuid = AsyncMock(return_value="puuid")
        self.riot.latest_match = AsyncMock(return_value="EUW_1")
        self.riot.report = AsyncMock(return_value=REPORT)
        self.client.riot = self.riot
        self.channel = MagicMock(spec=discord.TextChannel)
        self.channel.send = AsyncMock()
        self.channel_patch = patch.object(self.client, "get_channel", return_value=self.channel)
        self.channel_patch.start()

    async def asyncTearDown(self) -> None:
        self.channel_patch.stop()
        if self.client.state is not None:
            self.client.state.close()
        self.directory.cleanup()

    async def test_match_is_sent_only_once(self) -> None:
        await self.client.poll()
        await self.client.poll()
        self.channel.send.assert_awaited_once()
        self.riot.puuid.assert_awaited_once()

    async def test_failed_discord_send_can_be_retried(self) -> None:
        response = MagicMock(status=503, reason="Unavailable")
        self.channel.send.side_effect = discord.HTTPException(response, "Unavailable")
        with self.assertRaises(discord.HTTPException):
            await self.client.poll()
        assert self.client.state is not None
        self.assertIsNone(self.client.state.last_match())
        self.channel.send.side_effect = None
        await self.client.poll()
        self.assertEqual(self.client.state.last_match(), "EUW_1")

    async def test_testing_does_not_send(self) -> None:
        self.client.settings = Settings.from_env({**ENV, "ENVIRONMENT": "testing"})
        await self.client.poll()
        self.channel.send.assert_not_awaited()

    async def test_api_failure_does_not_stop_next_cycle(self) -> None:
        self.riot.latest_match.side_effect = [aiohttp.ClientConnectionError(), "EUW_1"]
        with (
            patch.object(self.client, "is_ready", return_value=True),
            patch("tracker.client.HEARTBEAT"),
        ):
            await self.client.monitor()
            await self.client.monitor()
        self.channel.send.assert_awaited_once()


class RiotTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_match_list(self) -> None:
        client = RiotClient(MagicMock())
        with patch.object(client, "get", new=AsyncMock(return_value=[])):
            self.assertIsNone(await client.latest_match("puuid"))

    async def test_http_error_is_not_disguised_as_no_match(self) -> None:
        client = RiotClient(MagicMock())
        with patch.object(client, "get", new=AsyncMock(side_effect=TimeoutError)):
            with self.assertRaises(TimeoutError):
                await client.latest_match("puuid")
