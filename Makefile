COMPOSE = docker compose
CHECK_IMAGE = lol-tracker-bot-check

.PHONY: build up down logs check check-build lint types test
build:
	$(COMPOSE) build
up:
	$(COMPOSE) up -d --build
down:
	$(COMPOSE) down
logs:
	$(COMPOSE) logs -f bot
check-build:
	docker build --pull --target development -t $(CHECK_IMAGE) .
lint:
	docker run --rm --network none $(CHECK_IMAGE) ruff check .
	docker run --rm --network none $(CHECK_IMAGE) ruff format --check .
types:
	docker run --rm --network none $(CHECK_IMAGE) mypy --cache-dir=/tmp/mypy
test:
	docker run --rm --network none $(CHECK_IMAGE) python -m unittest discover -s tests -v
check: check-build lint types test
