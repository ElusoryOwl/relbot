import logging

import discord
from discord import app_commands
from discord.ext import commands

from relbot.config import TEST_GUILD_ID
from relbot.db import cfg, close_db, init_db
from relbot.proposals import RelDynamic

log = logging.getLogger("relbot")

COGS = (
    "relbot.cogs.safety",
    "relbot.cogs.bonds",
    "relbot.cogs.profiles",
    "relbot.cogs.affection",
    "relbot.cogs.leaderboards",
    "relbot.cogs.admin",
    "relbot.cogs.maintenance",
)


class RelBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await init_db()
        self.add_dynamic_items(RelDynamic)

        @self.tree.error
        async def on_app_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            log.exception("Command failed: %s", interaction.command, exc_info=error)
            msg = "Something broke. Staff have the traceback in logs."
            if isinstance(error, app_commands.MissingPermissions):
                msg = "Manage Server required."
            elif isinstance(error, app_commands.CheckFailure):
                msg = "You can't use that here."
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            except Exception:
                log.debug("Could not notify user of command error")

        for ext in COGS:
            await self.load_extension(ext)

        if TEST_GUILD_ID:
            guild = discord.Object(id=TEST_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Synced commands to test guild %s and loaded cogs", TEST_GUILD_ID)
        else:
            await self.tree.sync()
            log.info("Synced commands globally and loaded cogs")

    async def on_ready(self):
        log.info("Ready as %s", self.user)

    async def close(self):
        await super().close()
        await close_db()


async def modlog(guild, text):
    if not guild:
        return
    row = await cfg(guild.id)
    ch_id = row["log_channel"]
    if not ch_id:
        return
    ch = guild.get_channel(ch_id)
    if ch:
        try:
            await ch.send(text[:1800])
        except Exception:
            log.exception("modlog failed")
