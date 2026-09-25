import discord
from discord import app_commands
from discord.ext import commands

from relbot.config import MAX_DATING, MAX_SPOUSES
from relbot.db import (
    are_related,
    count_kind,
    create_proposal,
    do_remove_parent,
    has_open_proposal,
    is_family,
    is_romantic,
    list_anniversaries_for,
    log_action,
    remove_relation,
)
from relbot.gates import gate_pair, proposal_on_cd
from relbot.proposals import RelDynamic


class Bonds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_proposal(self, interaction, member, kind):
        err = await gate_pair(interaction, member)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        if proposal_on_cd(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Slow down between proposals.", ephemeral=True)
            return
        gid = interaction.guild_id
        a, b = interaction.user.id, member.id
        if kind in ("dating", "marry", "adopt") and await is_family(gid, a, b):
            await interaction.response.send_message(
                "Already part of the same family bond."
                if kind == "adopt"
                else "Can't propose that — a family bond exists between you.",
                ephemeral=True,
            )
            return
        if kind == "adopt" and await is_romantic(gid, a, b):
            await interaction.response.send_message(
                "Can't adopt someone you're dating or married to.", ephemeral=True
            )
            return
        if kind == "marry" and await are_related(gid, a, b, "married"):
            await interaction.response.send_message("Already married.", ephemeral=True)
            return
        if kind == "dating" and await is_romantic(gid, a, b):
            await interaction.response.send_message("Already dating or married.", ephemeral=True)
            return
        if await has_open_proposal(gid, a, b, kind):
            await interaction.response.send_message(
                "There's already an open proposal between you two.", ephemeral=True
            )
            return
        pid = await create_proposal(gid, a, b, kind)
        if pid is None:
            await interaction.response.send_message(
                "There's already an open proposal between you two.", ephemeral=True
            )
            return
        view = discord.ui.View(timeout=None)
        view.add_item(RelDynamic("ok", pid))
        view.add_item(RelDynamic("no", pid))
        await interaction.response.send_message(
            f"{member.mention}, {interaction.user.mention} sent a **{kind}** proposal.",
            view=view,
        )

    @app_commands.command(description="Ask someone to date you")
    @app_commands.describe(member="Who you want to date")
    @app_commands.guild_only()
    async def date(self, interaction: discord.Interaction, member: discord.Member):
        if await count_kind(interaction.guild_id, interaction.user.id, "dating") >= MAX_DATING:
            await interaction.response.send_message("You're at your dating cap.", ephemeral=True)
            return
        await self.send_proposal(interaction, member, "dating")

    @app_commands.command(description="Propose marriage (multiple spouses allowed)")
    @app_commands.describe(member="Who you want to marry")
    @app_commands.guild_only()
    async def marry(self, interaction: discord.Interaction, member: discord.Member):
        if await count_kind(interaction.guild_id, interaction.user.id, "married") >= MAX_SPOUSES:
            await interaction.response.send_message("Spouse cap.", ephemeral=True)
            return
        await self.send_proposal(interaction, member, "marry")

    @app_commands.command(description="Divorce a spouse")
    @app_commands.describe(member="Spouse to divorce")
    @app_commands.guild_only()
    async def divorce(self, interaction: discord.Interaction, member: discord.Member):
        if not await are_related(interaction.guild_id, interaction.user.id, member.id, "married"):
            await interaction.response.send_message("Not married.", ephemeral=True)
            return
        await remove_relation(interaction.guild_id, interaction.user.id, member.id, "married")
        await log_action(interaction.guild_id, interaction.user.id, member.id, "divorce")
        await interaction.response.send_message(f"💔 {interaction.user.mention} divorced {member.mention}.")

    @app_commands.command(description="End a dating relationship")
    @app_commands.describe(member="Person you are dating")
    @app_commands.guild_only()
    async def breakup(self, interaction: discord.Interaction, member: discord.Member):
        if not await are_related(interaction.guild_id, interaction.user.id, member.id, "dating"):
            await interaction.response.send_message("Not dating.", ephemeral=True)
            return
        await remove_relation(interaction.guild_id, interaction.user.id, member.id, "dating")
        await log_action(interaction.guild_id, interaction.user.id, member.id, "breakup")
        await interaction.response.send_message(f"{interaction.user.mention} and {member.mention} broke up.")

    @app_commands.command(description="Ask to adopt someone (romantic bonds are blocked on this pair after)")
    @app_commands.describe(member="Who you want to adopt")
    @app_commands.guild_only()
    async def adopt(self, interaction: discord.Interaction, member: discord.Member):
        await self.send_proposal(interaction, member, "adopt")

    @app_commands.command(description="Remove someone you adopted")
    @app_commands.describe(member="Child to disown")
    @app_commands.guild_only()
    async def disown(self, interaction: discord.Interaction, member: discord.Member):
        if not await do_remove_parent(interaction.guild_id, interaction.user.id, member.id):
            await interaction.response.send_message("You are not their parent.", ephemeral=True)
            return
        await log_action(interaction.guild_id, interaction.user.id, member.id, "disown")
        await interaction.response.send_message(f"{interaction.user.mention} disowned {member.mention}.")

    @app_commands.command(description="Show your dating/marriage anniversaries, soonest first")
    @app_commands.guild_only()
    async def anniversaries(self, interaction: discord.Interaction):
        rows = await list_anniversaries_for(interaction.guild_id, interaction.user.id)
        if not rows:
            await interaction.response.send_message("You have no dating or married bonds yet.", ephemeral=True)
            return
        lines = []
        for r in rows:
            when = "🎉 today!" if r["days_away"] == 0 else f"in {r['days_away']}d"
            lines.append(f"<@{r['id']}> ({r['kind']}, since {r['since'][:10]}) — {when}")
        await interaction.response.send_message(
            embed=discord.Embed(title="Upcoming anniversaries", description="\n".join(lines), color=0xFF8FA3),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Bonds(bot))
