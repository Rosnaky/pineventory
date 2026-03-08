
from datetime import datetime, timedelta, timezone

import discord
from pydantic import ValidationError

from app.db.db_manager import DatabaseManager
from app.db.models import CheckoutRequest


class CheckoutsView(discord.ui.View):
    def __init__(self, item, checkouts):
        super().__init__(timeout=300)
        self.item = item
        self.checkouts = checkouts
        self.current_page = 0
        self.per_page = 8
        self.max_pages = max((len(checkouts) - 1) // self.per_page + 1, 1)

        if self.max_pages <= 1:
            self.previous_button.disabled = True
            self.next_button.disabled = True

    def create_embed(self, page: int) -> discord.Embed:
        start = page * self.per_page
        end = start + self.per_page
        page_checkouts = self.checkouts[start:end]

        embed = discord.Embed(
            title=f"Checkouts — {self.item.item_name}",
            color=discord.Color.orange(),
            description=f"{len(self.checkouts)} active checkout{'s' if len(self.checkouts) != 1 else ''}",
        )

        for co in page_checkouts:
            status = ""
            if co.is_overdue:
                status = " — **OVERDUE**"

            return_info = ""
            if co.expected_return_date:
                return_info = f"\nReturn by: {co.expected_return_date.strftime('%b %d, %Y')}"

            embed.add_field(
                name=f"Checkout #{co.id}  —  {co.quantity}x",
                value=(
                    f"<@{co.user_id}> · Since {co.checked_out_at.strftime('%b %d')}"
                    f" ({co.days_checked_out}d ago){status}"
                    f"{return_info}"
                    + (f"\n> {co.notes}" if co.notes else "")
                ),
                inline=False,
            )

        embed.set_footer(
            text=f"Page {page + 1}/{self.max_pages}"
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


class CheckoutModal(discord.ui.Modal, title="Checkout Item"):
    def __init__(self, item, db_manager: DatabaseManager):
        super().__init__()
        self.item = item
        self.db = db_manager

        self.quantity = discord.ui.TextInput(
            label="Quantity",
            placeholder=f"Max: {item.quantity_available}",
            default="1",
            min_length=1,
            max_length=5,
        )
        self.add_item(self.quantity)

        self.days = discord.ui.TextInput(
            label="Expected return in N days (optional)",
            placeholder="e.g., 7",
            required=False,
            min_length=1,
            max_length=3,
        )
        self.add_item(self.days)

        self.notes = discord.ui.TextInput(
            label="Notes (optional)",
            style=discord.TextStyle.paragraph,
            placeholder="Any notes about this checkout",
            required=False,
            max_length=500,
        )
        self.add_item(self.notes)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild_id:
            await interaction.followup.send(
                "This command can only be used in servers.",
                ephemeral=True
            )
            return
            

        try:
            quantity = int(self.quantity.value)
            days_value = int(self.days.value) if self.days.value else None

            await self.db.ensure_user_exists(interaction.user.id, interaction.user.name)

            expected_return = None
            if days_value:
                expected_return = datetime.now(timezone.utc) + timedelta(days=days_value)

            request = CheckoutRequest(
                item_id=self.item.id,
                quantity=quantity,
                expected_return_date=expected_return,
                notes=self.notes.value or None,
            )

            checkout = await self.db.checkout_item(request, interaction.guild_id, interaction.user.id)

            if not checkout:
                await interaction.followup.send(
                    "Checkout failed — not enough available.", ephemeral=True
                )
                return

            await interaction.followup.send(
                f"Checked out **{quantity}x {self.item.item_name}** (Checkout ID: {checkout.id})",
                ephemeral=True,
            )

        except ValidationError as e:
            errors = "\n".join(err["msg"] for err in e.errors())
            await interaction.followup.send(f"Validation error:\n{errors}", ephemeral=True)
        except ValueError:
            await interaction.followup.send("Invalid quantity or days.", ephemeral=True)
