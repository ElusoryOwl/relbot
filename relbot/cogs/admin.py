from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from relbot.db import backup_db, get_profile, list_actions, log_action, remove_relation, set_cfg, wipe_user
from relbot.views import ConfirmView


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(description="Staff tools: lock, log, wipe, force-break, relinfo, backup")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        action="Staff action to run",
        member="Target member",
        member2="Second member for force-break",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="lock", value="lock"),
            app_commands.Choice(name="unlock", value="unlock"),
            app_commands.Choice(name="set-log-here", value="log"),
            app_commands.Choice(name="force-break", value="break"),
            app_commands.Choice(name="wipe-user", value="wipe"),
            app_commands.Choice(name="relinfo", value="info"),
            app_commands.Choice(name="backup-now", value="backup"),
        ]
    )
    @app_commands.guild_only()
    async def reladmin(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        member: Optional[discord.Member] = None,
        member2: Optional[discord.Member] = None,
    ):
        gid = interaction.guild_id
        act = action.value
        if act == "lock":
            await set_cfg(gid, locked=1)
            await interaction.response.send_message("Relationship commands locked.")
        elif act == "unlock":
            await set_cfg(gid, locked=0)
            await interaction.response.send_message("Relationship commands unlocked.")
        elif act == "log":
            await set_cfg(gid, log_channel=interaction.channel_id)
            await interaction.response.send_message("Log channel set to here.")
        elif act == "break":
            if not member or not member2:
                await interaction.response.send_message("Need two members.", ephemeral=True)
                return
            await remove_relation(gid, member.id, member2.id, "married")
            await remove_relation(gid, member.id, member2.id, "dating")
            await log_action(gid, interaction.user.id, member.id, f"force-break:{member2.id}")
            await interaction.response.send_message("Bond removed.")
        elif act == "wipe":
            if not member:
                await interaction.response.send_message("Need member.", ephemeral=True)
                return
            view = ConfirmView(invoker_id=interaction.user.id)
            await interaction.response.send_message(
                f"This permanently deletes {member.mention}'s relationship data in this server. Continue?",
                view=view,
                ephemeral=True,
            )
            view._message = await interaction.original_response()
            await view.wait()
            if not view.confirmed:
                return
            await wipe_user(gid, member.id)
            await log_action(gid, interaction.user.id, member.id, "wipe")
            await interaction.followup.send(
                "Wiped relations, profile, nicknames, blocks, and proposals.", ephemeral=True
            )
        elif act == "info":
            if not member:
                await interaction.response.send_message("Need member.", ephemeral=True)
                return
            rows = await list_actions(gid, member.id)
            p = await get_profile(gid, member.id)
            lines = [f"`{r['ts'][:16]}` {r['cmd']} <@{r['actor']}> → <@{r['target']}>" for r in rows] or ["none"]
            await interaction.response.send_message(
                f"{member.mention} title={p['title'] or '—'} privacy={p['privacy']}\n" + "\n".join(lines),
                ephemeral=True,
            )
        elif act == "backup":
            await interaction.response.defer(ephemeral=True, thinking=True)
            path = await backup_db()
            await interaction.followup.send(f"Backup written to `{path}`.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
