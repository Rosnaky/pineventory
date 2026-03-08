from datetime import datetime, timedelta, timezone

import discord
from pydantic import ValidationError

from app.cogs.views.checkouts_view import CheckoutModal, CheckoutsView
from app.db.models import CheckoutRequest


class ItemDetailsView(discord.ui.View):
    def __init__(self, item, checkouts, db_manager):
        super().__init__(timeout=300)
        self.item = item
        self.checkouts = checkouts
        self.db = db_manager

        if item.quantity_available == 0:
            self.checkout_button.disabled = True
            self.checkout_button.label = "Unavailable"
            self.checkout_button.style = discord.ButtonStyle.secondary

        if not checkouts:
            self.view_checkouts_button.disabled = True
            self.view_checkouts_button.style = discord.ButtonStyle.secondary

    def create_embed(self) -> discord.Embed:
        item = self.item

        embed = discord.Embed(
            title=item.item_name,
            color=discord.Color.blue(),
            timestamp=item.updated_at or item.created_at,
        )

        if item.is_po_link:
            po_display = f"[View Thread]({item.purchase_order})"
        else:
            po_display = f"`{item.purchase_order}`"

        embed.add_field(
            name="Details",
            value=(
                f"**ID:** {item.id}\n"
                f"**Subteam:** {item.subteam.value.title()}\n"
                f"**Location:** {item.location}"
            ),
            inline=True,
        )

        embed.add_field(
            name="Quantity",
            value=(
                f"**Total:** {item.quantity_total}\n"
                f"**Available:** {item.quantity_available}\n"
                f"**Checked Out:** {item.quantity_checked_out}"
            ),
            inline=True,
        )

        embed.add_field(
            name="Info",
            value=(
                f"**Contact:** <@{item.point_of_contact}>\n"
                f"**PO:** {po_display}"
            ),
            inline=True,
        )

        if item.description:
            embed.add_field(name="Description", value=item.description, inline=False)

        embed.set_footer(text="Last updated")

        return embed

    @discord.ui.button(label="Checkout", style=discord.ButtonStyle.green)
    async def checkout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CheckoutModal(self.item, self.db)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="View Checkouts", style=discord.ButtonStyle.primary)
    async def view_checkouts_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CheckoutsView(self.item, self.checkouts)
        embed = view.create_embed(0)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
