FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/relationships.db

WORKDIR /app

RUN useradd --create-home --uid 1000 bot \
 && mkdir -p /data \
 && chown bot:bot /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY relbot ./relbot

USER bot
VOLUME ["/data"]

# The maintenance cog writes a heartbeat file every minute; this just
# checks it's recent. See relbot/healthcheck.py.
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
  CMD python -m relbot.healthcheck || exit 1

STOPSIGNAL SIGTERM
CMD ["python", "-u", "main.py"]
