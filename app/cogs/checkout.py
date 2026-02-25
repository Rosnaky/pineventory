# cogs/checkout.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from datetime import datetime, timedelta
from pydantic import ValidationError

from app.cogs.views.my_checkouts import MyCheckoutsView
from app.db.models import CheckoutRequest

class Checkout(commands.Cog):
    def __init__(self, bot, db_manager):
        self.bot = bot
        self.db = db_manager
    
    @app_commands.command(name="checkout", description="Check out an item")
    @app_commands.describe(
        item_id="The item ID to check out",
        quantity="How many to check out",
        days="Expected return in N days (optional)",
        notes="Any notes about the checkout (optional)"
    )
    async def checkout(
        self,
        interaction: discord.Interaction,
        item_id: int,
        quantity: int,
        days: Optional[int] = None,
        notes: Optional[str] = None
    ):
        await interaction.response.defer()
        
        await self.db.ensure_user_exists(interaction.user.id, interaction.user.name)
        
        item = await self.db.get_item(item_id)
        if not item:
            await interaction.followup.send("Item not found", ephemeral=True)
            return
        
        if item.quantity_available < quantity:
            await interaction.followup.send(
                f"Not enough available!\n"
                f"**{item.item_name}** - Available: {item.quantity_available}, Requested: {quantity}",
                ephemeral=True
            )
            return
        
        try:
            expected_return = None
            if days:
                expected_return = datetime.now() + timedelta(days=days)
            
            request = CheckoutRequest(
                item_id=item_id,
                quantity=quantity,
                expected_return_date=expected_return,
                notes=notes
            )
            
            checkout = await self.db.checkout_item(request, interaction.user.id)
            
            if not checkout:
                await interaction.followup.send("Checkout failed", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="Item Checked Out",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Item", value=item.item_name, inline=True)
            embed.add_field(name="Quantity", value=str(quantity), inline=True)
            embed.add_field(name="Checkout ID", value=str(checkout.id), inline=True)
            
            if expected_return:
                embed.add_field(
                    name="Expected Return",
                    value=f"<t:{int(expected_return.timestamp())}:D>",
                    inline=True
                )
            
            if notes:
                embed.add_field(name="Notes", value=notes, inline=False)
            
            embed.add_field(
                name="Remaining Available",
                value=f"{item.quantity_available - quantity} / {item.quantity_total}",
                inline=True
            )
            
            embed.set_footer(text=f"Checked out by {interaction.user.name}")
            
            await interaction.followup.send(embed=embed)
            
        except ValidationError as e:
            errors = "\n".join([f"• {err['loc'][0]}: {err['msg']}" for err in e.errors()])
            await interaction.followup.send(
                f"**Validation Error:**\n{errors}",
                ephemeral=True
            )
    
    @app_commands.command(name="return", description="Return a checked out item")
    @app_commands.describe(checkout_id="The checkout ID to return")
    async def return_item(self, interaction: discord.Interaction, checkout_id: int):
        await interaction.response.defer()
        
        success = await self.db.return_item(checkout_id, interaction.user.id)
        
        if not success:
            await interaction.followup.send(
                "Checkout not found or already returned!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="Item Returned",
            description=f"Checkout ID: {checkout_id}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Returned by {interaction.user.name}")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="mycheckouts", description="View your active checkouts")
    async def my_checkouts(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        checkouts = await self.db.get_active_checkouts(interaction.user.id)
        
        if not checkouts:
            await interaction.followup.send("📦 You have no active checkouts!")
            return
        
        embed = discord.Embed(
            title=f"📋 {interaction.user.name}'s Active Checkouts",
            color=discord.Color.blue(),
            description=f"Total: {len(checkouts)} checkout(s)"
        )
        
        for checkout in checkouts[:10]:
            item = await self.db.get_item(checkout.item_id)
            if not item:
                continue
            
            field_value = f"**Quantity:** {checkout.quantity}\n"
            field_value += f"**Checked out:** <t:{int(checkout.checked_out_at.timestamp())}:R>\n"
            
            if checkout.expected_return_date:
                field_value += f"**Expected return:** <t:{int(checkout.expected_return_date.timestamp())}:D>\n"
                if checkout.is_overdue:
                    field_value += "⚠️ **OVERDUE**\n"
            
            if checkout.notes:
                field_value += f"**Notes:** {checkout.notes[:50]}\n"
            
            field_value += f"**Checkout ID:** {checkout.id}"
            
            embed.add_field(
                name=f"{item.item_name}",
                value=field_value,
                inline=False
            )
        
        if len(checkouts) > 10:
            embed.set_footer(text=f"Showing 10 of {len(checkouts)} checkouts")
        
        view = MyCheckoutsView(checkouts[:10], self.db)
        
        await interaction.followup.send(embed=embed, view=view)
    
    @app_commands.command(name="allcheckouts", description="View all active checkouts")
    async def all_checkouts(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        checkouts = await self.db.get_active_checkouts()
        
        if not checkouts:
            await interaction.followup.send("No active checkouts!")
            return
        
        embed = discord.Embed(
            title="📋 All Active Checkouts",
            color=discord.Color.blue(),
            description=f"Total: {len(checkouts)} active checkout(s)"
        )
        
        user_checkouts = {}
        for checkout in checkouts:
            if checkout.user_id not in user_checkouts:
                user_checkouts[checkout.user_id] = []
            user_checkouts[checkout.user_id].append(checkout)
        
        for user_id, user_cos in list(user_checkouts.items())[:10]:
            items_text = []
            for co in user_cos[:3]:
                item = await self.db.get_item(co.item_id)
                if item:
                    overdue = "⚠️ " if co.is_overdue else ""
                    items_text.append(f"{overdue}{item.item_name} x{co.quantity}")
            
            if len(user_cos) > 3:
                items_text.append(f"... and {len(user_cos) - 3} more")
            
            embed.add_field(
                name=f"<@{user_id}>",
                value="\n".join(items_text) if items_text else "No items",
                inline=True
            )
        
        if len(user_checkouts) > 10:
            embed.set_footer(text=f"Showing 10 of {len(user_checkouts)} users")
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Checkout(bot, bot.db))