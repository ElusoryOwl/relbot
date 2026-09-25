import discord
from discord import app_commands
from discord.ext import commands

from relbot.db import couple_kind, list_heat_lb, list_lust_lb, list_married_lb


class Leaderboards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(description="Rate compatibility between two members")
    @app_commands.describe(one="First member", two="Second member")
    @app_commands.guild_only()
    async def compatibility(self, interaction: discord.Interaction, one: discord.Member, two: discord.Member):
        score = (one.id + two.id) % 101
        if await couple_kind(interaction.guild_id, one.id, two.id):
            score = min(100, score + 20)
        await interaction.response.send_message(f"{one.mention} × {two.mention}: **{score}%**")

    @app_commands.command(description="Leaderboard of members with the most spouses")
    @app_commands.guild_only()
    async def marriedlb(self, interaction: discord.Interaction):
        rows = await list_married_lb(interaction.guild_id)
        if not rows:
            await interaction.response.send_message("Empty.")
            return
        desc = "\n".join(f"**{i}.** <@{r['user_id']}> — {r['n']}" for i, r in enumerate(rows, 1))
        await interaction.response.send_message(embed=discord.Embed(title="Married", description=desc))

    @app_commands.command(description="Leaderboard of couples with the highest lust")
    @app_commands.guild_only()
    async def lustlb(self, interaction: discord.Interaction):
        rows = await list_lust_lb(interaction.guild_id)
        if not rows:
            await interaction.response.send_message("Empty.")
            return
        desc = "\n".join(
            f"**{i}.** <@{r['user_a']}> × <@{r['user_b']}> — {r['lust']}" for i, r in enumerate(rows, 1)
        )
        await interaction.response.send_message(
            embed=discord.Embed(title="Lust", description=desc, color=0xFF0A54)
        )

    @app_commands.command(description="Leaderboard of members with the highest heat")
    @app_commands.guild_only()
    async def heatlb(self, interaction: discord.Interaction):
        rows = await list_heat_lb(interaction.guild_id)
        desc = "\n".join(f"**{i}.** <@{r['user_id']}> — {r['heat']}" for i, r in enumerate(rows, 1)) or "Empty."
        await interaction.response.send_message(embed=discord.Embed(title="Heat", description=desc))

    @app_commands.command(description="List relationship and NSFW commands")
    @app_commands.guild_only()
    async def relhelp(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "**Safety:** `/optin` `/optout` `/forgetme` `/stop` `/block` `/privacy` `/profileprivacy` `/freeuse` `/setsafeword`\n"
            "**Bonds:** `/date` `/marry` `/divorce` `/breakup` `/adopt` `/disown` `/relationship`\n"
            "**Lewd:** `/fuck` `/tease` `/spank` `/blow` `/ride` `/breed` `/claim` `/leash` `/scene` `/aftercare`\n"
            "`/privacy` = lewd output. `/profileprivacy` = kink card. `/forgetme` erases your data here.\n"
            "**Staff:** `/reladmin`",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Leaderboards(bot))
