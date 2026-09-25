from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from relbot.config import BIO_MAX, EMBED_FIELD_MAX, NICKNAME_MAX, TITLE_MAX
from relbot.db import (
    children_of,
    get_nickname,
    get_partners,
    get_profile,
    parents_of,
    set_nickname,
    set_prof,
)
from relbot.gates import profile_visible_to


def clip(text: str, limit: int = EMBED_FIELD_MAX) -> str:
    text = text or "—"
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


class Profiles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(description="Hide your bio, title, and nicknames from other members")
    @app_commands.describe(mode="Who can see your profile card")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="public", value="public"),
            app_commands.Choice(name="private", value="private"),
        ]
    )
    @app_commands.guild_only()
    async def privacy(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        await set_prof(interaction.guild_id, interaction.user.id, privacy=mode.value)
        await interaction.response.send_message(f"Profile privacy: {mode.value}", ephemeral=True)

    @app_commands.command(description="Set a short title shown next to your name in scenes")
    @app_commands.describe(title="Short title, e.g. 'the Ever Clumsy'")
    @app_commands.guild_only()
    async def settitle(self, interaction: discord.Interaction, title: str):
        await set_prof(interaction.guild_id, interaction.user.id, title=title[:TITLE_MAX])
        await interaction.response.send_message("Title set.", ephemeral=True)

    @app_commands.command(description="Set the bio shown on your profile")
    @app_commands.describe(text="A short bio")
    @app_commands.guild_only()
    async def setbio(self, interaction: discord.Interaction, text: str):
        await set_prof(interaction.guild_id, interaction.user.id, bio=text[:BIO_MAX])
        await interaction.response.send_message("Saved.", ephemeral=True)

    @app_commands.command(description="Give someone a pet name shown on your profile")
    @app_commands.describe(member="Who to nickname", nickname="Leave blank to clear it")
    @app_commands.guild_only()
    async def nickname(
        self, interaction: discord.Interaction, member: discord.Member, nickname: Optional[str] = None
    ):
        clean = nickname[:NICKNAME_MAX] if nickname else None
        await set_nickname(interaction.guild_id, interaction.user.id, member.id, clean)
        if clean:
            await interaction.response.send_message(f"{member.mention} is now '{clean}' to you.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Cleared your nickname for {member.mention}.", ephemeral=True)

    @app_commands.command(description="Show bonds, streaks, bio, and nicknames")
    @app_commands.describe(member="Whose profile to show")
    @app_commands.guild_only()
    async def relationship(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        member = member or interaction.user
        gid = interaction.guild_id
        viewer_id = interaction.user.id
        p = await get_profile(gid, member.id)
        hide_card = not await profile_visible_to(gid, viewer_id, member.id)

        async def lst(people, spicy=False):
            if not people:
                return "None"
            out = []
            for x in people:
                nick = await get_nickname(gid, viewer_id, x["id"])
                m = interaction.guild.get_member(x["id"])
                label = f"'{nick}' " if nick else ""
                if m is None:
                    try:
                        m = await self.bot.fetch_user(x["id"])
                    except discord.HTTPException:
                        out.append(f"{label}(unknown user) ({x['since'][:10]})")
                        continue
                s = f"{label}{m.mention} ({x['since'][:10]}"
                if spicy:
                    s += f" ❤️{x.get('affection', 0)}"
                    streak = x.get("streak", 0)
                    if streak:
                        s += f" 🔥{streak}d"
                out.append(s + ")")
            return clip("\n".join(out), EMBED_FIELD_MAX)

        married = await get_partners(gid, member.id, "married")
        dating = await get_partners(gid, member.id, "dating")

        embed = discord.Embed(title=f"{member.display_name}", color=0xFF4D6D)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name=f"Married ({len(married)})", value=await lst(married, True), inline=False)
        embed.add_field(name=f"Dating ({len(dating)})", value=await lst(dating, True), inline=False)
        embed.add_field(name="Kids", value=await lst(await children_of(gid, member.id)), inline=False)
        embed.add_field(name="Parents", value=await lst(await parents_of(gid, member.id)), inline=False)
        embed.add_field(name="Title", value=clip(p["title"] or "—", 256), inline=True)
        if hide_card:
            embed.add_field(name="Bio", value="Hidden (private profile).", inline=False)
        else:
            embed.add_field(name="Bio", value=clip(p["bio"] or "—"), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=hide_card)


async def setup(bot):
    await bot.add_cog(Profiles(bot))
