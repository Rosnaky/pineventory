from datetime import datetime, timedelta

import discord
from pydantic import ValidationError

from app.db.models import CheckoutRequest


class ItemDetailsView(discord.ui.View):
    def __init__(self, item, db_manager):
        super().__init__(timeout=300)
        self.item = item
        self.db = db_manager
    
    @discord.ui.button(label="📤 Checkout", style=discord.ButtonStyle.green)
    async def checkout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CheckoutModal(self.item, self.db)
        await interaction.response.send_modal(modal)

class CheckoutModal(discord.ui.Modal, title="Checkout Item"):
    def __init__(self, item, db_manager):
        super().__init__()
        self.item = item
        self.db = db_manager
        
        self.quantity = discord.ui.TextInput(
            label="Quantity",
            placeholder=f"Max: {item.quantity_available}",
            default="1",
            min_length=1,
            max_length=5
        )
        self.add_item(self.quantity)
        
        self.days = discord.ui.TextInput(
            label="Expected return in N days (optional)",
            placeholder="e.g., 7",
            required=False,
            min_length=1,
            max_length=3
        )
        self.add_item(self.days)
        
        self.notes = discord.ui.TextInput(
            label="Notes (optional)",
            style=discord.TextStyle.paragraph,
            placeholder="Any notes about this checkout",
            required=False,
            max_length=500
        )
        self.add_item(self.notes)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            quantity = int(self.quantity.value)
            days_value = int(self.days.value) if self.days.value else None
            
            await self.db.ensure_user_exists(interaction.user.id, interaction.user.name)
            
            expected_return = None
            if days_value:
                expected_return = datetime.now() + timedelta(days=days_value)
            
            request = CheckoutRequest(
                item_id=self.item.id,
                quantity=quantity,
                expected_return_date=expected_return,
                notes=self.notes.value or None
            )
            
            checkout = await self.db.checkout_item(request, interaction.user.id)
            
            if not checkout:
                await interaction.followup.send("Checkout failed! Not enough available.", ephemeral=True)
                return
            
            await interaction.followup.send(
                f"Checked out {quantity}x **{self.item.item_name}**\nCheckout ID: {checkout.id}",
                ephemeral=True
            )
            
        except ValidationError as e:
            errors = "\n".join([f"• {err['msg']}" for err in e.errors()])
            await interaction.followup.send(f"Validation Error:\n{errors}", ephemeral=True)
        except ValueError:
            await interaction.followup.send("Invalid quantity or days!", ephemeral=True)
            