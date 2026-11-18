"""Appels Riot asynchrones et validation des réponses."""

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

import aiohttp


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("Objet JSON Riot attendu")
    return {str(key): item for key, item in value.items()}


def number(value: object) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError("Nombre Riot attendu")
    return float(value)


def text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Texte Riot attendu")
    return value


def generate_score(participant: dict[str, object], duration_seconds: float) -> int:
    duration = max(1, duration_seconds / 60)
    kills = number(participant.get("kills", 0))
    deaths = number(participant.get("deaths", 0))
    assists = number(participant.get("assists", 0))
    kda = min(40, (kills + assists) / max(1, deaths) * 8)
    if participant.get("individualPosition") == "UTILITY":
        resources = min(30, number(participant.get("visionScore", 0)) / duration / 1.5 * 30)
    else:
        cs = number(participant.get("totalMinionsKilled", 0)) + number(
            participant.get("neutralMinionsKilled", 0)
        )
        resources = min(30, cs / duration / 8 * 30)
    challenges = mapping(participant.get("challenges", {}))
    impact = min(30, number(challenges.get("killParticipation", 0)) * 50)
    result = kda + resources + impact + (10 if participant.get("win") else -10)
    return max(0, min(100, int(result)))


@dataclass(frozen=True)
class MatchReport:
    champion: str
    mode: str
    lane: str
    win: bool
    score: int
    kills: int
    deaths: int
    assists: int
    duration: int
    ended_at: str
    surrender: bool


def parse_report(payload: object, puuid: str) -> MatchReport:
    info = mapping(mapping(payload)["info"])
    participants = info["participants"]
    if not isinstance(participants, list):
        raise ValueError("Liste des participants absente")
    for item in participants:
        player = mapping(item)
        if player.get("puuid") != puuid:
            continue
        duration = number(info["gameDuration"])
        return MatchReport(
            champion=text(player["championName"]),
            mode={420: "Solo / Duo", 440: "Flex 5v5", 400: "Draft", 450: "ARAM"}.get(
                int(number(info["queueId"])), "Autre"
            ),
            lane={
                "TOP": "Toplane",
                "JUNGLE": "Jungle",
                "MIDDLE": "Midlane",
                "BOTTOM": "Adc",
                "UTILITY": "Support",
            }.get(text(player.get("individualPosition", "")), "Inconnue"),
            win=bool(player["win"]),
            score=generate_score(player, duration),
            kills=int(number(player["kills"])),
            deaths=int(number(player["deaths"])),
            assists=int(number(player["assists"])),
            duration=int(duration // 60),
            ended_at=datetime.fromtimestamp(
                number(info["gameEndTimestamp"]) / 1000, tz=ZoneInfo("Europe/Paris")
            ).strftime("%d/%m/%Y %H:%M"),
            surrender=bool(player.get("gameEndedInSurrender"))
            or bool(player.get("gameEndedInEarlySurrender")),
        )
    raise ValueError("Joueur absent du match")


class RiotClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session

    async def get(self, path: str) -> object:
        async with self.session.get(f"https://europe.api.riotgames.com{path}") as response:
            response.raise_for_status()
            payload: object = await response.json()
            return payload

    async def puuid(self, game_name: str, tag_line: str) -> str:
        path = f"/riot/account/v1/accounts/by-riot-id/{quote(game_name, safe='')}/{quote(tag_line, safe='')}"
        return text(mapping(await self.get(path))["puuid"])

    async def latest_match(self, puuid: str) -> str | None:
        payload = await self.get(
            f"/lol/match/v5/matches/by-puuid/{quote(puuid, safe='')}/ids?count=1"
        )
        if not isinstance(payload, list):
            raise ValueError("Liste de matchs Riot attendue")
        return text(payload[0]) if payload else None

    async def report(self, match_id: str, puuid: str) -> MatchReport:
        return parse_report(
            await self.get(f"/lol/match/v5/matches/{quote(match_id, safe='')}"), puuid
        )
