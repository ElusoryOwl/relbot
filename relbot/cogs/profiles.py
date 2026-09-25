from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from relbot.config import EMBED_FIELD_MAX
from relbot.db import (
    children_of,
    get_partners,
    get_profile,
    parents_of,
    set_prof,
)
from relbot.gates import profile_visible_to
from relbot.lines import clip


class Profiles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(description="Who can see your lewd command results")
    @app_commands.describe(mode="public posts in channel, private is only visible to you")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="public", value="public"),
            app_commands.Choice(name="private", value="private"),
        ]
    )
    @app_commands.guild_only()
    async def privacy(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        await set_prof(interaction.guild_id, interaction.user.id, privacy=mode.value)
        await interaction.response.send_message(f"Lewd output privacy: {mode.value}", ephemeral=True)

    @app_commands.command(description="Hide your kinks and limits from other members")
    @app_commands.describe(mode="Who can see your profile card")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="public", value="public"),
            app_commands.Choice(name="private", value="private"),
        ]
    )
    @app_commands.guild_only()
    async def profileprivacy(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        await set_prof(interaction.guild_id, interaction.user.id, profile_privacy=mode.value)
        await interaction.response.send_message(f"Profile privacy: {mode.value}", ephemeral=True)

    @app_commands.command(description="Allow opted-in strangers to use lewd commands on you")
    @app_commands.describe(state="Turn free-use on or off")
    @app_commands.choices(
        state=[
            app_commands.Choice(name="on", value="on"),
            app_commands.Choice(name="off", value="off"),
        ]
    )
    @app_commands.guild_only()
    async def freeuse(self, interaction: discord.Interaction, state: app_commands.Choice[str]):
        if state.value == "on":
            await set_prof(interaction.guild_id, interaction.user.id, freeuse=1, opted=1)
        else:
            await set_prof(interaction.guild_id, interaction.user.id, freeuse=0)
        await interaction.response.send_message(f"Free-use {state.value}.", ephemeral=True)

    @app_commands.command(description="Set a title used in scene text")
    @app_commands.describe(title="Short title inserted into scene text")
    @app_commands.guild_only()
    async def settitle(self, interaction: discord.Interaction, title: str):
        await set_prof(interaction.guild_id, interaction.user.id, title=title[:32])
        await interaction.response.send_message("Title set.", ephemeral=True)

    @app_commands.command(description="Set the kinks shown on your profile")
    @app_commands.describe(text="Your kinks")
    @app_commands.guild_only()
    async def setkinks(self, interaction: discord.Interaction, text: str):
        await set_prof(interaction.guild_id, interaction.user.id, kinks=text[:500])
        await interaction.response.send_message("Saved.", ephemeral=True)

    @app_commands.command(description="Set the limits shown on your profile")
    @app_commands.describe(text="Your limits")
    @app_commands.guild_only()
    async def setlimits(self, interaction: discord.Interaction, text: str):
        await set_prof(interaction.guild_id, interaction.user.id, limits=text[:500])
        await interaction.response.send_message("Saved.", ephemeral=True)

    @app_commands.command(description="Set the safeword shown on your profile")
    @app_commands.describe(word="Safeword shown on your profile")
    @app_commands.guild_only()
    async def setsafeword(self, interaction: discord.Interaction, word: str):
        await set_prof(interaction.guild_id, interaction.user.id, safeword=word[:40])
        await interaction.response.send_message("Saved.", ephemeral=True)

    @app_commands.command(description="Show bonds, heat, kinks, and opt-in status")
    @app_commands.describe(member="Whose profile to show")
    @app_commands.guild_only()
    async def relationship(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        member = member or interaction.user
        gid = interaction.guild_id
        p = await get_profile(gid, member.id)
        hide_card = not await profile_visible_to(gid, interaction.user.id, member.id)

        async def lst(people, spicy=False):
            if not people:
                return "None"
            out = []
            for x in people:
                m = interaction.guild.get_member(x["id"])
                if m is None:
                    try:
                        m = await self.bot.fetch_user(x["id"])
                    except discord.NotFound:
                        out.append(f"(deleted user) ({x['since'][:10]})")
                        continue
                s = f"{m.mention} ({x['since'][:10]}"
                if spicy:
                    s += f" ❤️{x.get('affection', 0)} 🔥{x.get('lust', 0)}"
                out.append(s + ")")
            return clip("\n".join(out), EMBED_FIELD_MAX)

        embed = discord.Embed(title=f"{member.display_name}", color=0xFF4D6D)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name=f"Married ({len(await get_partners(gid, member.id, 'married'))})",
            value=await lst(await get_partners(gid, member.id, "married"), True),
            inline=False,
        )
        embed.add_field(
            name=f"Dating ({len(await get_partners(gid, member.id, 'dating'))})",
            value=await lst(await get_partners(gid, member.id, "dating"), True),
            inline=False,
        )
        embed.add_field(name="Kids", value=await lst(await children_of(gid, member.id)), inline=False)
        embed.add_field(name="Parents", value=await lst(await parents_of(gid, member.id)), inline=False)
        embed.add_field(name="Heat", value=str(p["heat"]), inline=True)
        embed.add_field(name="Opt-in", value="yes" if p["opted"] else "no", inline=True)
        embed.add_field(name="Free-use", value="yes" if p["freeuse"] else "no", inline=True)
        embed.add_field(name="Title", value=clip(p["title"] or "—", 256), inline=True)
        if hide_card:
            embed.add_field(name="Kinks / limits", value="Hidden (private profile).", inline=False)
        else:
            embed.add_field(name="Safeword", value=clip(p["safeword"] or "red", 256), inline=True)
            embed.add_field(name="Kinks", value=clip(p["kinks"] or "—"), inline=False)
            embed.add_field(name="Limits", value=clip(p["limits"] or "—"), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=hide_card)

    @app_commands.command(description="Show someone's kinks, limits, and safeword")
    @app_commands.describe(member="Whose kink card to show")
    @app_commands.guild_only()
    async def kinks(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        member = member or interaction.user
        gid = interaction.guild_id
        p = await get_profile(gid, member.id)
        hide_card = not await profile_visible_to(gid, interaction.user.id, member.id)
        e = discord.Embed(title=f"{member.display_name}'s card", color=0xC9184A)
        if hide_card:
            e.description = "This profile is private."
        else:
            e.add_field(name="Kinks", value=clip(p["kinks"] or "—"), inline=False)
            e.add_field(name="Limits", value=clip(p["limits"] or "—"), inline=False)
            e.add_field(name="Safeword", value=p["safeword"] or "red")
            e.add_field(name="Free-use", value="yes" if p["freeuse"] else "no")
        await interaction.response.send_message(embed=e, ephemeral=hide_card)


async def setup(bot):
    await bot.add_cog(Profiles(bot))
