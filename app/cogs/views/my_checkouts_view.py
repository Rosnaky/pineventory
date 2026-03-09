import discord

from app.utils.logger import logger


class MyCheckoutsView(discord.ui.View):
    def __init__(self, checkouts, items_by_id: dict, db_manager):
        super().__init__(timeout=300)
        self.checkouts = checkouts
        self.items_by_id = items_by_id
        self.db = db_manager
        self.current_page = 0
        self.per_page = 5
        self.max_pages = max((len(self.checkouts) - 1) // self.per_page + 1, 1)
        self.selected_checkout_id = None

        if self.max_pages <= 1:
            self.previous_button.disabled = True
            self.next_button.disabled = True

        self.confirm_button.disabled = True
        self.cancel_button.disabled = True
        self._build_return_select()

    def _build_return_select(self):
        page_checkouts = self._page_checkouts()
        if not page_checkouts:
            return

        options = []
        for co in page_checkouts:
            item_name = self.items_by_id.get(co.item_id, "Unknown")
            label = f"{item_name} — {co.quantity}x (#{co.id})"
            options.append(discord.SelectOption(label=label[:100], value=str(co.id)))

        self.return_select.options = options

    def _page_checkouts(self):
        start = self.current_page * self.per_page
        return self.checkouts[start : start + self.per_page]

    def _selected_checkout(self):
        if self.selected_checkout_id is None:
            return None
        return next((co for co in self.checkouts if co.id == self.selected_checkout_id), None)

    def create_embed(self, user_display: str) -> discord.Embed:
        page_checkouts = self._page_checkouts()
        total = len(self.checkouts)

        embed = discord.Embed(
            title=f"{user_display}'s Active Checkouts",
            color=discord.Color.blue(),
            description=f"{total} active checkout{'s' if total != 1 else ''}",
        )

        for co in page_checkouts:
            item_name = self.items_by_id.get(co.item_id, "Unknown")
            status = " — **OVERDUE**" if co.is_overdue else ""
            selected = " ◀" if co.id == self.selected_checkout_id else ""

            lines = [
                f"**{co.quantity}x** · Checked out <t:{int(co.checked_out_at.timestamp())}:R>",
            ]

            if co.expected_return_date:
                lines[0] += f"{status}"
                lines.append(
                    f"Return by: <t:{int(co.expected_return_date.timestamp())}:D>"
                )

            if co.notes:
                lines.append(f"> {co.notes[:80]}")

            embed.add_field(
                name=f"{item_name}  —  Checkout #{co.id}{selected}",
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages}")
        return embed

    @discord.ui.select(
        placeholder="Select a checkout to return",
        options=[discord.SelectOption(label="placeholder", value="0")],
    )
    async def return_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_checkout_id = int(select.values[0])
        self.confirm_button.disabled = False
        self.cancel_button.disabled = False

        await interaction.response.edit_message(
            embed=self.create_embed(interaction.user.display_name), view=self
        )

    @discord.ui.button(label="Confirm Return", style=discord.ButtonStyle.danger, row=2)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = interaction.guild_id
        co = self._selected_checkout()

        if not guild_id or not co:
            await interaction.response.send_message("Something went wrong.", ephemeral=True)
            return

        success = await self.db.return_item(co.id, guild_id, interaction.user.id)

        if not success:
            await interaction.response.send_message("Failed to return item.", ephemeral=True)
            return

        self.checkouts = [c for c in self.checkouts if c.id != co.id]
        self.selected_checkout_id = None
        self.confirm_button.disabled = True
        self.cancel_button.disabled = True
        self.max_pages = max((len(self.checkouts) - 1) // self.per_page + 1, 1)

        if self.current_page >= self.max_pages:
            self.current_page = max(self.max_pages - 1, 0)

        if not self.checkouts:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title=f"{interaction.user.display_name}'s Active Checkouts",
                    color=discord.Color.blue(),
                    description="No active checkouts.",
                ),
                view=None,
            )
            return

        self._build_return_select()
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_pages - 1

        await interaction.response.edit_message(
            embed=self.create_embed(interaction.user.display_name), view=self
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=2)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.selected_checkout_id = None
        self.confirm_button.disabled = True
        self.cancel_button.disabled = True

        await interaction.response.edit_message(
            embed=self.create_embed(interaction.user.display_name), view=self
        )

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, row=3)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.selected_checkout_id = None
            self.confirm_button.disabled = True
            self.cancel_button.disabled = True
            self.previous_button.disabled = self.current_page == 0
            self.next_button.disabled = False
            self._build_return_select()
            await interaction.response.edit_message(
                embed=self.create_embed(interaction.user.display_name), view=self
            )
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=3)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self.selected_checkout_id = None
            self.confirm_button.disabled = True
            self.cancel_button.disabled = True
            self.next_button.disabled = self.current_page >= self.max_pages - 1
            self.previous_button.disabled = False
            self._build_return_select()
            await interaction.response.edit_message(
                embed=self.create_embed(interaction.user.display_name), view=self
            )
        else:
            await interaction.response.defer()
