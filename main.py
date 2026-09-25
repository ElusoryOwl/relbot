import asyncio
import logging
import os
import signal

from relbot.bot import RelBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("relbot")


def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN is not set")

    bot = RelBot()

    # Let discord.py own SIGINT/SIGTERM so bot.close() runs.
    # Do not register a custom SIGTERM handler — that replaces the
    # default terminate behavior and Docker will have to SIGKILL.
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()