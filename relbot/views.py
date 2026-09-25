import discord


class ConfirmView(discord.ui.View):
    """A Yes/No prompt for a destructive action. Only the original
    invoker can press a button; it disables itself after use or after
    timing out."""

    def __init__(self, *, invoker_id: int, timeout: float = 30):
        super().__init__(timeout=timeout)
        self.invoker_id = invoker_id
        self.confirmed: bool | None = None
        self._message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
            return False
        return True

    def _disable_all(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self._disable_all()
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self._disable_all()
        await interaction.response.edit_message(content="Cancelled.", view=self)
        self.stop()

    async def on_timeout(self):
        self.confirmed = False
        self._disable_all()
        if self._message:
            try:
                await self._message.edit(content="Timed out, nothing changed.", view=self)
            except discord.HTTPException:
                pass
