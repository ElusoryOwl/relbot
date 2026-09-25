import logging
import os

from discord.ext import commands, tasks

from relbot.config import BACKUP_INTERVAL_HOURS, HEARTBEAT_PATH
from relbot.db import backup_db, prune_actions
from relbot.gates import sweep_cooldowns

log = logging.getLogger("relbot.maintenance")


class Maintenance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldown_sweep.start()
        self.action_prune.start()
        self.heartbeat.start()
        self.backup.start()

    def cog_unload(self):
        self.cooldown_sweep.cancel()
        self.action_prune.cancel()
        self.heartbeat.cancel()
        self.backup.cancel()

    @tasks.loop(minutes=30)
    async def cooldown_sweep(self):
        sweep_cooldowns()

    @tasks.loop(hours=24)
    async def action_prune(self):
        deleted = await prune_actions()
        if deleted:
            log.info("Pruned %s old action rows", deleted)

    @tasks.loop(minutes=1)
    async def heartbeat(self):
        # Docker's HEALTHCHECK just checks this file's mtime; a Discord
        # bot has no HTTP endpoint of its own to probe, so this is the
        # simplest reliable "am I actually alive" signal available.
        try:
            os.makedirs(os.path.dirname(HEARTBEAT_PATH) or ".", exist_ok=True)
            with open(HEARTBEAT_PATH, "w") as f:
                f.write(str(self.bot.latency))
        except OSError:
            log.exception("Could not write heartbeat file at %s", HEARTBEAT_PATH)

    @tasks.loop(hours=BACKUP_INTERVAL_HOURS)
    async def backup(self):
        try:
            path = await backup_db()
            log.info("Wrote scheduled backup to %s", path)
        except Exception:
            log.exception("Scheduled backup failed")

    @cooldown_sweep.before_loop
    @action_prune.before_loop
    @heartbeat.before_loop
    @backup.before_loop
    async def before_loops(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Maintenance(bot))
