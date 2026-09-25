import io
import json
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from relbot.config import STOP_MINUTES
from relbot.db import add_block, del_block, export_user, log_action, now, set_prof, wipe_user
from relbot.views import ConfirmView


class Safety(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(description="Freeze bonds/proposals/interactions involving you for 30 minutes")
    @app_commands.guild_only()
    async def stop(self, interaction: discord.Interaction):
        until = (now() + timedelta(minutes=STOP_MINUTES)).isoformat()
        await set_prof(interaction.guild_id, interaction.user.id, stopped_until=until)
        await interaction.response.send_message(
            f"{interaction.user.mention} used /stop. Proposals and interactions involving them "
            f"are paused for {STOP_MINUTES}m."
        )

    @app_commands.command(description="Block someone from proposals and interactions")
    @app_commands.describe(member="Person to block")
    @app_commands.guild_only()
    async def block(self, interaction: discord.Interaction, member: discord.Member):
        if member.id == interaction.user.id:
            await interaction.response.send_message("You can't block yourself.", ephemeral=True)
            return
        await add_block(interaction.guild_id, interaction.user.id, member.id)
        await interaction.response.send_message(f"Blocked {member.mention}.", ephemeral=True)

    @app_commands.command(description="Unblock someone")
    @app_commands.describe(member="Person to unblock")
    @app_commands.guild_only()
    async def unblock(self, interaction: discord.Interaction, member: discord.Member):
        await del_block(interaction.guild_id, interaction.user.id, member.id)
        await interaction.response.send_message("Unblocked.", ephemeral=True)

    @app_commands.command(description="Delete your relationship data in this server")
    @app_commands.guild_only()
    async def forgetme(self, interaction: discord.Interaction):
        view = ConfirmView(invoker_id=interaction.user.id)
        await interaction.response.send_message(
            "This permanently deletes your bonds, profile, nicknames, blocks, and proposals "
            "in this server. This can't be undone. Continue?",
            view=view,
            ephemeral=True,
        )
        view._message = await interaction.original_response()
        await view.wait()
        if not view.confirmed:
            return
        await wipe_user(interaction.guild_id, interaction.user.id)
        await log_action(interaction.guild_id, interaction.user.id, interaction.user.id, "forgetme")
        await interaction.followup.send(
            "Deleted your profile, bonds, nicknames, blocks, and proposals in this server.",
            ephemeral=True,
        )

    @app_commands.command(description="Download a copy of what this bot stores about you here")
    @app_commands.guild_only()
    async def exportme(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        data = await export_user(interaction.guild_id, interaction.user.id)
        buf = io.BytesIO(json.dumps(data, indent=2, default=str).encode("utf-8"))
        await interaction.followup.send(
            "Here's everything stored about you in this server.",
            file=discord.File(buf, filename="relbot-data-export.json"),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Safety(bot))
