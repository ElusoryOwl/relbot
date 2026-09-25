import random
from datetime import timedelta
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from relbot.bot import modlog
from relbot.db import (
    add_heat,
    add_stats,
    cfg,
    couple_kind,
    get_profile,
    log_action,
    now,
    now_iso,
    parse_iso,
    set_prof,
)
from relbot.gates import display_name, gate_pair, on_cd, send_result
from relbot.lines import LINES, fill_line
from relbot.media import fetch_for_sentence


async def scene_embed(key: str, sentence: str, line_tag: str | None, color: int = 0xFF4D6D):
    try:
        async with aiohttp.ClientSession() as session:
            img = await fetch_for_sentence(session, key, sentence, line_tag)
        if not img:
            return None
        embed = discord.Embed(color=color)
        embed.set_image(url=img)
        return embed
    except Exception:
        return None


def pick_line(key: str, intensity: Optional[str] = None):
    pack = LINES[key]
    if isinstance(pack, dict):
        intensity = intensity or "vanilla"
        choices = pack.get(intensity, pack["vanilla"])
    else:
        choices = pack
    item = random.choice(choices)
    if isinstance(item, tuple):
        return item[0], item[1]
    return item, None


async def lewd_act(
    interaction,
    member,
    key,
    aff,
    lust,
    ha,
    hb,
    require_together=True,
    claim=False,
    intensity: Optional[str] = None,
):
    err = await gate_pair(
        interaction, member, lewd=True, require_together=require_together, allow_freeuse=True
    )
    if err:
        await interaction.response.send_message(err, ephemeral=True)
        return
    if on_cd(interaction.guild_id, interaction.user.id):
        await interaction.response.send_message("Slow down.", ephemeral=True)
        return
    gid = interaction.guild_id
    template, line_tag = pick_line(key, intensity)
    text = fill_line(template, display_name(interaction.user, gid), display_name(member, gid))
    kind = couple_kind(gid, interaction.user.id, member.id)
    extra = ""
    if kind:
        add_stats(gid, interaction.user.id, member.id, kind, aff, lust)
        extra += f" (+{aff} aff / +{lust} lust)"
    h1 = add_heat(gid, interaction.user.id, ha)
    h2 = add_heat(gid, member.id, hb)
    extra += f"\nHeat {h1} / {h2}"
    if claim:
        p = get_profile(gid, member.id)
        set_prof(gid, member.id, holes_claimed=p["holes_claimed"] + 1)
    set_prof(gid, interaction.user.id, last_lewd=now_iso(), last_lewd_with=member.id)
    set_prof(gid, member.id, last_lewd=now_iso(), last_lewd_with=interaction.user.id)
    log_action(gid, interaction.user.id, member.id, key)
    embed = await scene_embed(key, text, line_tag)
    await send_result(interaction, text + extra, gid, interaction.user.id, member.id, embed=embed)
    await modlog(interaction.guild, f"`/{key}` {interaction.user} → {member}")


class Lewd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(description="Fuck a partner; pick vanilla, rough, or degrading")
    @app_commands.describe(member="Partner", intensity="How rough the scene is")
    @app_commands.choices(
        intensity=[
            app_commands.Choice(name="vanilla", value="vanilla"),
            app_commands.Choice(name="rough", value="rough"),
            app_commands.Choice(name="degrading", value="degrading"),
        ]
    )
    @app_commands.guild_only()
    async def fuck(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        intensity: Optional[app_commands.Choice[str]] = None,
    ):
        await lewd_act(
            interaction,
            member,
            "fuck",
            6,
            15,
            8,
            12,
            intensity=(intensity.value if intensity else "vanilla"),
        )

    @app_commands.command(description="Tease or edge someone you're involved with")
    @app_commands.describe(member="Partner")
    @app_commands.guild_only()
    async def tease(self, interaction: discord.Interaction, member: discord.Member):
        await lewd_act(interaction, member, "tease", 4, 10, 6, 14)

    @app_commands.command(description="Spank someone you're involved with")
    @app_commands.describe(member="Partner")
    @app_commands.guild_only()
    async def spank(self, interaction: discord.Interaction, member: discord.Member):
        await lewd_act(interaction, member, "spank", 3, 8, 4, 10)

    @app_commands.command(description="Give head to someone you're involved with")
    @app_commands.describe(member="Partner")
    @app_commands.guild_only()
    async def blow(self, interaction: discord.Interaction, member: discord.Member):
        await lewd_act(interaction, member, "blow", 5, 14, 10, 12)

    @app_commands.command(description="Ride someone you're involved with")
    @app_commands.describe(member="Partner")
    @app_commands.guild_only()
    async def ride(self, interaction: discord.Interaction, member: discord.Member):
        await lewd_act(interaction, member, "ride", 6, 16, 12, 10)

    @app_commands.command(description="Breed someone you're involved with")
    @app_commands.describe(member="Partner")
    @app_commands.guild_only()
    async def breed(self, interaction: discord.Interaction, member: discord.Member):
        await lewd_act(interaction, member, "breed", 8, 20, 10, 16, claim=True)

    @app_commands.command(description="Publicly claim someone you're involved with")
    @app_commands.describe(member="Partner")
    @app_commands.guild_only()
    async def claim(self, interaction: discord.Interaction, member: discord.Member):
        await lewd_act(interaction, member, "claim", 5, 12, 6, 10, claim=True)

    @app_commands.command(description="Leash / pet-play flavor with a partner")
    @app_commands.describe(member="Partner")
    @app_commands.guild_only()
    async def leash(self, interaction: discord.Interaction, member: discord.Member):
        await lewd_act(interaction, member, "leash", 4, 9, 5, 11)

    @app_commands.command(description="Kiss someone")
    @app_commands.describe(member="Person to kiss")
    @app_commands.guild_only()
    async def kiss(self, interaction: discord.Interaction, member: discord.Member):
        await lewd_act(interaction, member, "kiss", 3, 3, 3, 3, require_together=False)

    @app_commands.command(description="Hug someone")
    @app_commands.describe(member="Person to hug")
    @app_commands.guild_only()
    async def hug(self, interaction: discord.Interaction, member: discord.Member):
        err = await gate_pair(interaction, member, lewd=False)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        text = f"🤗 {interaction.user.mention} hugs {member.mention}."
        embed = await scene_embed("hug", text, "hug", color=0xFFB3C1)
        await interaction.response.send_message(text, embed=embed)

    @app_commands.command(description="Aftercare; requires a shared lewd act in the last 2 hours")
    @app_commands.describe(member="Person to care for")
    @app_commands.guild_only()
    async def aftercare(self, interaction: discord.Interaction, member: discord.Member):
        err = await gate_pair(interaction, member, lewd=True, require_together=False, allow_freeuse=True)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        gid = interaction.guild_id
        pa = get_profile(gid, interaction.user.id)
        pb = get_profile(gid, member.id)
        recent_a = parse_iso(pa["last_lewd"])
        recent_b = parse_iso(pb["last_lewd"])
        pair_ok = (
            pa["last_lewd_with"] == member.id
            and pb["last_lewd_with"] == interaction.user.id
            and recent_a
            and recent_b
            and now() - recent_a <= timedelta(hours=2)
            and now() - recent_b <= timedelta(hours=2)
        )
        if not pair_ok:
            await interaction.response.send_message("No recent shared scene between you two.", ephemeral=True)
            return
        kind = couple_kind(gid, interaction.user.id, member.id)
        if kind:
            add_stats(gid, interaction.user.id, member.id, kind, 10, 0)
        h1 = add_heat(gid, interaction.user.id, -15)
        h2 = add_heat(gid, member.id, -20)
        text = f"🤍 {interaction.user.mention} does aftercare for {member.mention}. Heat {h1}/{h2}"
        embed = await scene_embed("aftercare", text, "aftercare", color=0xFFE5EC)
        await send_result(interaction, text, gid, interaction.user.id, member.id, embed=embed)

    @app_commands.command(description="Start a random explicit scene")
    @app_commands.describe(member="Other person in the scene")
    @app_commands.guild_only()
    async def scene(self, interaction: discord.Interaction, member: discord.Member):
        conf = cfg(interaction.guild_id)
        req = not conf["allow_stranger_scene"]
        await lewd_act(interaction, member, "scene", 2, 8, 7, 7, require_together=req)


async def setup(bot):
    await bot.add_cog(Lewd(bot))