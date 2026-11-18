FROM python:3.12-slim AS dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.txt

FROM python:3.12-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN groupadd --gid 10001 bot && useradd --uid 10001 --gid bot --no-create-home bot \
    && mkdir /data && chown bot:bot /data
COPY --from=dependencies /opt/venv /opt/venv
COPY bot.py .
COPY tracker ./tracker
USER bot
HEALTHCHECK --interval=60s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import pathlib,time; p=pathlib.Path('/tmp/lol-tracker-heartbeat'); exit(0 if p.exists() and time.time()-float(p.read_text())<180 else 1)"
CMD ["python", "bot.py"]

FROM runtime AS development
ENV RUFF_CACHE_DIR=/tmp/ruff
USER root
COPY requirements-dev.txt requirements.txt ./
RUN pip install -r requirements-dev.txt
COPY pyproject.toml .
COPY tests ./tests
USER bot

FROM runtime AS production
