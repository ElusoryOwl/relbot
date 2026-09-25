from datetime import datetime
from typing import Optional

import discord

from relbot.config import ADULT_ROLE_NAME, LEWD_COOLDOWN_SEC
from relbot.db import cfg, couple_kind, either_blocked, get_profile, is_family, now, parse_iso

_last_cmd: dict[tuple[int, int], datetime] = {}


def adult_role_label(guild: Optional[discord.Guild], guild_id: int) -> str:
    row = cfg(guild_id)
    rid = row["adult_role_id"]
    if rid and guild:
        role = guild.get_role(rid)
        if role:
            return role.mention
    return f"`{row['adult_role'] or ADULT_ROLE_NAME}`"


def has_adult_role(member: discord.Member, guild_id: int) -> bool:
    row = cfg(guild_id)
    rid = row["adult_role_id"]
    if rid:
        return any(r.id == rid for r in member.roles)
    name = (row["adult_role"] or ADULT_ROLE_NAME).lower()
    return any(r.name.lower() == name for r in member.roles)


def stopped(gid, uid) -> bool:
    p = get_profile(gid, uid)
    t = parse_iso(p["stopped_until"])
    return bool(t and t > now())


def on_cd(gid, uid):
    key = (gid, uid)
    t = _last_cmd.get(key)
    if t and (now() - t).total_seconds() < LEWD_COOLDOWN_SEC:
        return True
    _last_cmd[key] = now()
    return False


def sweep_cooldowns():
    cutoff = now().timestamp() - LEWD_COOLDOWN_SEC * 4
    stale = [k for k, t in _last_cmd.items() if t.timestamp() < cutoff]
    for k in stale:
        _last_cmd.pop(k, None)


async def gate_pair(interaction, target, lewd=False, require_together=False, allow_freeuse=False):
    gid = interaction.guild_id
    actor = interaction.user
    if not interaction.guild:
        return "Guild only."
    if cfg(gid)["locked"] and lewd:
        return "Lewd commands are locked by staff."
    if target.bot or target.id == actor.id:
        return "No."
    if either_blocked(gid, actor.id, target.id):
        return "Blocked."
    if stopped(gid, actor.id) or stopped(gid, target.id):
        return "Someone used /stop. Wait it out."
    if lewd:
        if not getattr(interaction.channel, "nsfw", False):
            return "NSFW channel only."
        if not isinstance(actor, discord.Member) or not has_adult_role(actor, gid) or not has_adult_role(target, gid):
            return f"Both users need the {adult_role_label(interaction.guild, gid)} role."
        if is_family(gid, actor.id, target.id):
            return "Lewd commands are disabled on parent/child bonds."
        tp = get_profile(gid, target.id)
        free = allow_freeuse and tp["freeuse"]
        if require_together and not couple_kind(gid, actor.id, target.id) and not free:
            return "Date/marry them first, or they need free-use on."
    return None


def display_name(member, gid):
    title = get_profile(gid, member.id)["title"] or ""
    title = title.replace("{", "").replace("}", "")
    return f"{title} {member.mention}".strip() if title else member.mention


def public_ok(gid, *user_ids):
    return all(get_profile(gid, u)["privacy"] != "private" for u in user_ids)


def profile_visible_to(gid, viewer_id, subject_id) -> bool:
    if viewer_id == subject_id:
        return True
    return get_profile(gid, subject_id)["profile_privacy"] != "private"


async def send_result(interaction, text, gid, *uids, embed=None):
    eph = not public_ok(gid, *uids)
    kwargs = {"ephemeral": eph}
    if embed is not None:
        kwargs["embed"] = embed
    if interaction.response.is_done():
        await interaction.followup.send(text, **kwargs)
    else:
        await interaction.response.send_message(text, **kwargs)