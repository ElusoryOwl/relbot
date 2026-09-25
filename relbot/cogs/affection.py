import random

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from relbot.bot import modlog
from relbot.db import add_affection, couple_kind, log_action
from relbot.gates import display_name, gate_pair, on_cd
from relbot.media import fetch_tagged_image

COMPLIMENTS = [
    "{a} tells {b} they've been doing great lately.",
    "{a} says {b}'s smile makes their day better.",
    "{a} reminds {b} how proud they are of them.",
    "{a} tells {b} they're one of their favorite people.",
]


def fill(template: str, a: str, b: str) -> str:
    return (
        template.replace("{a}", "\x00A\x00")
        .replace("{b}", "\x00B\x00")
        .replace("\x00A\x00", a)
        .replace("\x00B\x00", b)
    )


async def tagged_embed(tag: str, color: int):
    try:
        async with aiohttp.ClientSession() as session:
            url = await fetch_tagged_image(session, tag)
        if not url:
            return None
        embed = discord.Embed(color=color)
        embed.set_image(url=url)
        return embed
    except Exception:
        return None


async def affection_act(interaction, member, tag, text_template, affection_gain, color, log_key=None):
    err = await gate_pair(interaction, member)
    if err:
        await interaction.response.send_message(err, ephemeral=True)
        return
    if on_cd(interaction.guild_id, interaction.user.id):
        await interaction.response.send_message("Slow down.", ephemeral=True)
        return

    gid = interaction.guild_id
    a_name = await display_name(interaction.user, gid)
    b_name = await display_name(member, gid)
    text = fill(text_template, a_name, b_name)

    kind = await couple_kind(gid, interaction.user.id, member.id)
    if kind and affection_gain:
        streak = await add_affection(gid, interaction.user.id, member.id, kind, affection_gain)
        if streak and streak > 1:
            text += f"\n🔥 {streak}-day streak!"

    embed = await tagged_embed(tag, color)
    await interaction.response.send_message(text, embed=embed)
    await log_action(gid, interaction.user.id, member.id, log_key or tag)
    await modlog(interaction.guild, f"`/{log_key or tag}` {interaction.user} → {member}")


class Affection(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(description="Hug someone")
    @app_commands.describe(member="Person to hug")
    @app_commands.guild_only()
    async def hug(self, interaction: discord.Interaction, member: discord.Member):
        await affection_act(interaction, member, "hug", "🤗 {a} hugs {b}.", 3, 0xFFB3C1)

    @app_commands.command(description="Cuddle up with someone you're involved with")
    @app_commands.describe(member="Person to cuddle")
    @app_commands.guild_only()
    async def cuddle(self, interaction: discord.Interaction, member: discord.Member):
        await affection_act(interaction, member, "cuddle", "🥰 {a} cuddles up with {b}.", 4, 0xFFC2D1)

    @app_commands.command(description="Pat someone on the head")
    @app_commands.describe(member="Person to pat")
    @app_commands.guild_only()
    async def pat(self, interaction: discord.Interaction, member: discord.Member):
        await affection_act(interaction, member, "pat", "✋ {a} pats {b} on the head.", 2, 0xFFE5EC)

    @app_commands.command(description="Give someone a kiss on the cheek")
    @app_commands.describe(member="Person to kiss")
    @app_commands.guild_only()
    async def kiss(self, interaction: discord.Interaction, member: discord.Member):
        await affection_act(interaction, member, "kiss", "😘 {a} kisses {b} on the cheek.", 4, 0xFF4D6D)

    @app_commands.command(description="Poke someone")
    @app_commands.describe(member="Person to poke")
    @app_commands.guild_only()
    async def poke(self, interaction: discord.Interaction, member: discord.Member):
        await affection_act(interaction, member, "poke", "👉 {a} pokes {b}.", 1, 0xB8C0FF)

    @app_commands.command(description="High-five someone")
    @app_commands.describe(member="Person to high-five")
    @app_commands.guild_only()
    async def highfive(self, interaction: discord.Interaction, member: discord.Member):
        await affection_act(interaction, member, "highfive", "🙌 {a} high-fives {b}.", 1, 0xFFD670)

    @app_commands.command(description="Compliment someone you're involved with")
    @app_commands.describe(member="Person to compliment")
    @app_commands.guild_only()
    async def compliment(self, interaction: discord.Interaction, member: discord.Member):
        template = random.choice(COMPLIMENTS)
        await affection_act(interaction, member, "wave", template, 3, 0xFFE5EC, log_key="compliment")


async def setup(bot):
    await bot.add_cog(Affection(bot))
