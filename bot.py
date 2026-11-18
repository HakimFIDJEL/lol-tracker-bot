"""Point d'entrée, sans connexion lors d'un import."""

import logging

from tracker.client import TrackerClient
from tracker.config import Settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = Settings.from_env()
    TrackerClient(settings).run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
