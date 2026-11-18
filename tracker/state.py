"""État persistant et verrou exclusif pour une seule instance."""

import fcntl
import json
from pathlib import Path
from typing import TextIO


class StateStore:
    def __init__(self, directory: Path, identity: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "state.json"
        self.identity = identity
        self.lock: TextIO = (directory / "bot.lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise RuntimeError("Une autre instance utilise déjà cet état") from None

    def last_match(self) -> str | None:
        if not self.path.exists():
            return None
        data: object = json.loads(self.path.read_text())
        if not isinstance(data, dict):
            raise ValueError("État persistant invalide")
        if data.get("identity") != self.identity:
            return None
        match_id: object = data.get("last_match")
        if not isinstance(match_id, str):
            raise ValueError("Identifiant de match invalide dans l'état")
        return match_id

    def save(self, match_id: str) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"identity": self.identity, "last_match": match_id}))
        temporary.replace(self.path)

    def close(self) -> None:
        self.lock.close()
