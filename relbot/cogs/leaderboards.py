import discord
from discord import app_commands
from discord.ext import commands

from relbot.db import couple_kind, list_affection_lb, list_married_lb, list_streak_lb


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

    @app_commands.command(description="Leaderboard of couples with the highest affection")
    @app_commands.guild_only()
    async def affectionlb(self, interaction: discord.Interaction):
        rows = await list_affection_lb(interaction.guild_id)
        if not rows:
            await interaction.response.send_message("Empty.")
            return
        desc = "\n".join(
            f"**{i}.** <@{r['user_a']}> × <@{r['user_b']}> — {r['affection']}" for i, r in enumerate(rows, 1)
        )
        await interaction.response.send_message(
            embed=discord.Embed(title="Affection", description=desc, color=0xFF4D6D)
        )

    @app_commands.command(description="Leaderboard of couples with the longest daily interaction streak")
    @app_commands.guild_only()
    async def streaklb(self, interaction: discord.Interaction):
        rows = await list_streak_lb(interaction.guild_id)
        if not rows:
            await interaction.response.send_message("Empty.")
            return
        desc = "\n".join(
            f"**{i}.** <@{r['user_a']}> × <@{r['user_b']}> — {r['streak']}d" for i, r in enumerate(rows, 1)
        )
        await interaction.response.send_message(
            embed=discord.Embed(title="Streaks", description=desc, color=0xFFD670)
        )

    @app_commands.command(description="List relationship commands")
    @app_commands.guild_only()
    async def relhelp(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "**Safety:** `/forgetme` `/exportme` `/stop` `/block` `/unblock`\n"
            "**Bonds:** `/date` `/marry` `/divorce` `/breakup` `/adopt` `/disown` "
            "`/relationship` `/anniversaries`\n"
            "**Affection:** `/hug` `/cuddle` `/pat` `/kiss` `/poke` `/highfive` `/compliment`\n"
            "**Profile:** `/settitle` `/setbio` `/nickname` `/privacy`\n"
            "**Boards:** `/marriedlb` `/affectionlb` `/streaklb` `/compatibility`\n"
            "**Staff:** `/reladmin`",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Leaderboards(bot))
