import discord

from app.db.models import Item


class InventoryPaginatedView(discord.ui.View):
    def __init__(self, items: list[Item], db_manager):
        super().__init__(timeout=300)
        self.items = items
        self.db = db_manager
        self.current_page = 0
        self.items_per_page = 5
        self.max_pages = max((len(items) - 1) // self.items_per_page + 1, 1)

        if self.max_pages <= 1:
            self.previous_button.disabled = True
            self.next_button.disabled = True

    def create_embed(self, page: int) -> discord.Embed:
        start = page * self.items_per_page
        end = start + self.items_per_page
        page_items = self.items[start:end]

        embed = discord.Embed(
            title="Inventory",
            color=discord.Color.from_rgb(47, 49, 54),
        )

        for item in page_items:
            checked_out = (
                f"  ({item.quantity_checked_out} out)" if item.quantity_checked_out > 0 else ""
            )

            if item.is_po_link:
                po_display = f"PO: [Link]({item.purchase_order})"
            else:
                po_display = f"PO: `{item.purchase_order}`"

            lines = [
                f"`{item.subteam.value.title()}` · `{item.location}` · {po_display}",
                f"**{item.quantity_available}** / {item.quantity_total} available{checked_out}",
                f"Contact: <@{item.point_of_contact}>",
            ]

            if item.description:
                desc = item.description[:100] + ("…" if len(item.description) > 100 else "")
                lines.append(f"> {desc}")

            embed.add_field(
                name=f"{item.item_name}  —  ID {item.id}",
                value="\n".join(lines),
                inline=False,
            )

        total = len(self.items)
        embed.set_footer(
            text=f"Page {page + 1}/{self.max_pages}  ·  {total} item{'s' if total != 1 else ''}"
        )

        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.previous_button.disabled = self.current_page == 0
            self.next_button.disabled = False
            await interaction.response.edit_message(
                embed=self.create_embed(self.current_page), view=self
            )
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self.next_button.disabled = self.current_page == self.max_pages - 1
            self.previous_button.disabled = False
            await interaction.response.edit_message(
                embed=self.create_embed(self.current_page), view=self
            )
        else:
            await interaction.response.defer()
