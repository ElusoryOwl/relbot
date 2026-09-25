"""Standalone healthcheck used by the Docker HEALTHCHECK instruction.

A Discord bot has no HTTP endpoint of its own to probe, so the
maintenance cog writes a heartbeat file once a minute and this script
just checks that file's age. Exits 0 (healthy) if the heartbeat is
recent, non-zero otherwise. Deliberately avoids importing discord.py so
it starts instantly inside the container.
"""

import os
import sys
import time

from relbot.config import HEARTBEAT_PATH

MAX_AGE_SEC = 120


def main() -> None:
    try:
        age = time.time() - os.path.getmtime(HEARTBEAT_PATH)
    except OSError:
        sys.exit(1)
    sys.exit(0 if age < MAX_AGE_SEC else 1)


if __name__ == "__main__":
    main()
