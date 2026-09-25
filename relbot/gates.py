from datetime import datetime
from typing import Optional

from relbot.config import INTERACTION_COOLDOWN_SEC, PROPOSAL_COOLDOWN_SEC
from relbot.db import cfg, either_blocked, get_profile, now, parse_iso

# Per-(guild, user) cooldown trackers. In-memory by design (see README):
# resets on restart, not shared across processes, which is fine at this
# project's target scale of one process / a handful of servers.
_last_cmd: dict[tuple[int, int], datetime] = {}
_last_proposal: dict[tuple[int, int], datetime] = {}


def on_cd(gid, uid) -> bool:
    """Per-user cooldown for affection commands (hug/pat/cuddle/...)."""
    key = (gid, uid)
    t = _last_cmd.get(key)
    if t and (now() - t).total_seconds() < INTERACTION_COOLDOWN_SEC:
        return True
    _last_cmd[key] = now()
    return False


def proposal_on_cd(gid, uid) -> bool:
    """Per-user cooldown between /date, /marry, /adopt so one person can't
    blast proposals at many targets back to back."""
    key = (gid, uid)
    t = _last_proposal.get(key)
    if t and (now() - t).total_seconds() < PROPOSAL_COOLDOWN_SEC:
        return True
    _last_proposal[key] = now()
    return False


def sweep_cooldowns():
    """Drop cooldown entries old enough that they can no longer block
    anything, so these dicts don't grow forever on a busy bot."""
    cutoff = now().timestamp() - max(INTERACTION_COOLDOWN_SEC, PROPOSAL_COOLDOWN_SEC) * 4
    for store in (_last_cmd, _last_proposal):
        stale = [k for k, t in store.items() if t.timestamp() < cutoff]
        for k in stale:
            store.pop(k, None)


async def stopped(gid, uid) -> bool:
    p = await get_profile(gid, uid)
    t = parse_iso(p["stopped_until"])
    return bool(t and t > now())


async def gate_pair(interaction, target) -> Optional[str]:
    """Common checks shared by proposals (date/marry/adopt) and affection
    commands. Returns an error string to show the user, or None if OK."""
    if not interaction.guild:
        return "Guild only."
    gid = interaction.guild_id
    actor = interaction.user
    if target.bot or target.id == actor.id:
        return "No."
    row = await cfg(gid)
    if row["locked"]:
        return "Relationship commands are paused by staff."
    if await either_blocked(gid, actor.id, target.id):
        return "Blocked."
    if await stopped(gid, actor.id) or await stopped(gid, target.id):
        return "Someone used /stop. Wait it out."
    return None


async def display_name(member, gid) -> str:
    profile = await get_profile(gid, member.id)
    title = (profile["title"] or "").replace("{", "").replace("}", "")
    return f"{title} {member.mention}".strip() if title else member.mention


async def profile_visible_to(gid, viewer_id, subject_id) -> bool:
    if viewer_id == subject_id:
        return True
    profile = await get_profile(gid, subject_id)
    return profile["privacy"] != "private"
