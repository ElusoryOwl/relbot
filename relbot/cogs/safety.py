from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from relbot.config import STOP_MINUTES
from relbot.db import add_block, del_block, get_profile, log_action, now, set_prof, wipe_user


class Safety(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(description="Opt into lewd relationship commands")
    @app_commands.guild_only()
    async def optin(self, interaction: discord.Interaction):
        await set_prof(interaction.guild_id, interaction.user.id, opted=1)
        await interaction.response.send_message("You're opted in.", ephemeral=True)

    @app_commands.command(description="Opt out of lewd commands")
    @app_commands.guild_only()
    async def optout(self, interaction: discord.Interaction):
        await set_prof(interaction.guild_id, interaction.user.id, opted=0, freeuse=0)
        await interaction.response.send_message("Opted out. Free-use off.", ephemeral=True)

    @app_commands.command(description="Delete your relationship data in this server")
    @app_commands.guild_only()
    async def forgetme(self, interaction: discord.Interaction):
        await wipe_user(interaction.guild_id, interaction.user.id)
        await log_action(interaction.guild_id, interaction.user.id, interaction.user.id, "forgetme")
        await interaction.response.send_message(
            "Deleted your profile, bonds, blocks, and proposals in this server.",
            ephemeral=True,
        )

    @app_commands.command(description="Freeze lewd commands on you for 30 minutes")
    @app_commands.guild_only()
    async def stop(self, interaction: discord.Interaction):
        until = (now() + timedelta(minutes=STOP_MINUTES)).isoformat()
        await set_prof(interaction.guild_id, interaction.user.id, stopped_until=until)
        await interaction.response.send_message(
            f"{interaction.user.mention} used /stop. Lewd involving them is frozen for {STOP_MINUTES}m."
        )
        p = await get_profile(interaction.guild_id, interaction.user.id)
        await interaction.followup.send(
            f"Safeword on file: **{p['safeword'] or 'red'}**",
            ephemeral=True,
        )

    @app_commands.command(description="Block someone from proposals and lewd commands")
    @app_commands.describe(member="Person to block")
    @app_commands.guild_only()
    async def block(self, interaction: discord.Interaction, member: discord.Member):
        await add_block(interaction.guild_id, interaction.user.id, member.id)
        await interaction.response.send_message(f"Blocked {member.mention}.", ephemeral=True)

    @app_commands.command(description="Unblock someone")
    @app_commands.describe(member="Person to unblock")
    @app_commands.guild_only()
    async def unblock(self, interaction: discord.Interaction, member: discord.Member):
        await del_block(interaction.guild_id, interaction.user.id, member.id)
        await interaction.response.send_message("Unblocked.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Safety(bot))
