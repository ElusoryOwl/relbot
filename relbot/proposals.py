import logging

import discord

from relbot.db import (
    add_parent,
    add_relation,
    are_related,
    count_kind,
    either_blocked,
    get_proposal,
    is_family,
    is_romantic,
    log_action,
    remove_relation,
    reopen_proposal,
    try_close_proposal,
)
from relbot.config import MAX_DATING, MAX_SPOUSES

log = logging.getLogger("relbot.proposals")


class RelDynamic(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"rel(?P<act>ok|no):(?P<pid>[0-9]+)",
):
    def __init__(self, act: str, pid: int):
        self.act = act
        self.pid = pid
        super().__init__(
            discord.ui.Button(
                label="Accept" if act == "ok" else "Decline",
                style=discord.ButtonStyle.success if act == "ok" else discord.ButtonStyle.danger,
                custom_id=f"rel{act}:{pid}",
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["act"], int(match["pid"]))

    async def callback(self, interaction: discord.Interaction):
        await resolve_proposal(interaction, self.pid, self.act == "ok")


async def resolve_proposal(interaction, pid, accepted):
    from relbot.bot import modlog

    p = await get_proposal(pid)
    if not p or not p["open"]:
        await interaction.response.send_message("This proposal is closed.", ephemeral=True)
        return
    if interaction.user.id != p["to_id"]:
        await interaction.response.send_message("Not your proposal.", ephemeral=True)
        return
    if not await try_close_proposal(pid):
        await interaction.response.send_message("This proposal is closed.", ephemeral=True)
        return

    a, b, kind, gid = p["from_id"], p["to_id"], p["kind"], p["guild_id"]

    if not accepted:
        await interaction.response.edit_message(content="Proposal declined.", view=None)
        return

    hard_fail = None
    if await either_blocked(gid, a, b):
        hard_fail = "Can't finalize — one of you has blocked the other."
    elif kind in ("marry", "dating", "adopt") and await is_family(gid, a, b):
        hard_fail = (
            "Already part of the same family bond."
            if kind == "adopt"
            else "Can't finalize — a family bond exists between you."
        )
    elif kind == "adopt" and await is_romantic(gid, a, b):
        hard_fail = "Can't adopt someone you're dating or married to."
    elif kind == "marry" and await are_related(gid, a, b, "married"):
        hard_fail = "Already married."
    elif kind == "dating" and await is_romantic(gid, a, b):
        hard_fail = "Already dating or married."

    if hard_fail:
        await interaction.response.edit_message(content=hard_fail, view=None)
        return

    if kind == "marry":
        if await count_kind(gid, a, "married") >= MAX_SPOUSES or await count_kind(gid, b, "married") >= MAX_SPOUSES:
            await reopen_proposal(pid)
            await interaction.response.send_message("Spouse cap reached. Proposal still open.", ephemeral=True)
            return
        if await are_related(gid, a, b, "dating"):
            await remove_relation(gid, a, b, "dating")
        await add_relation(gid, a, b, "married")
        msg = f"💍 <@{a}> and <@{b}> are married."
    elif kind == "dating":
        if await count_kind(gid, a, "dating") >= MAX_DATING or await count_kind(gid, b, "dating") >= MAX_DATING:
            await reopen_proposal(pid)
            await interaction.response.send_message("Dating cap reached. Proposal still open.", ephemeral=True)
            return
        await add_relation(gid, a, b, "dating")
        msg = f"💗 <@{a}> and <@{b}> are dating."
    else:
        await add_parent(gid, a, b)
        msg = f"🏠 <@{a}> adopted <@{b}>."

    await log_action(gid, a, b, f"accept-{kind}")
    await interaction.response.edit_message(content=msg, view=None)
    await modlog(interaction.guild, msg)
