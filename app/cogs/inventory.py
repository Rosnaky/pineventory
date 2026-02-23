
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands
from pydantic import ValidationError

from app.cogs.views.delete_confirmation_view import DeleteConfirmationView
from app.cogs.views.inventory_paginated_view import InventoryPaginatedView
from app.cogs.views.item_details_view import ItemDetailsView
from app.db.models import CreateItemRequest, Subteam, UpdateItemRequest

class Inventory(commands.Cog):
    def __init__(self, bot, db_manager):
        self.bot = bot
        self.db = db_manager

    @app_commands.command(name="additem", description="Add a new item to inventory")
    @app_commands.describe(
        item_name="Name of the item",
        quantity="How many to add",
        location="Where is it stored",
        subteam="Which subteam owns it",
        point_of_contact="Team member responsible (mention them)",
        purchase_order="Discord PO thread link (preferred) or PO number",
        description="Optional description"
    )
    @app_commands.choices(
        subteam=[
            app_commands.Choice(name=member.value.title(), value=member.value)
            for member in Subteam
        ]
    )
    async def add_item(
        self,
        interaction: discord.Interaction,
        item_name: str,
        quantity: int,
        location: str,
        subteam: str,
        point_of_contact: discord.Member,
        purchase_order: str,
        description: Optional[str] = None
    ):
        await interaction.response.defer()

        await self.db.ensure_user_exists(interaction.user.id, interaction.user.name)
        await self.db.ensure_user_exists(point_of_contact.id, point_of_contact.name)

        try:
            request = CreateItemRequest(
                item_name=item_name,
                quantity=quantity,
                location=location,
                subteam=Subteam(subteam),
                point_of_contact=point_of_contact.id,
                purchase_order=purchase_order,
                description=description
            )

            item = await self.db.add_item(request, interaction.user.id)

            embed = discord.Embed(
                title="Item Added to Inventory",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Item", value=item.item_name, inline=True)
            embed.add_field(name="Quantity", value=str(item.quantity_total), inline=True)
            embed.add_field(name="Location", value=item.location, inline=True)
            embed.add_field(name="Subteam", value=item.subteam, inline=True)
            embed.add_field(name="Point of Contact", value=f"<@{item.point_of_contact}>", inline=True)
            embed.add_field(name="Purchase Order", value=item.purchase_order, inline=True)

            if item.description:
                embed.add_field(name="Description", value=item.description, inline=False)
            
            embed.set_footer(text=f"Item ID: {item.id} - Added by {interaction.user.name}")

            await interaction.followup.send(embed=embed)

        except ValidationError as e:
            errors = "\n".join([f"• {err['loc'][0]}: {err['msg']}" for err in e.errors()])
            await interaction.followup.send(
                f"**Validation Error:**\n{errors}",
                ephemeral=True
            )

    @app_commands.command(name="inventory", description="View inventory items")
    @app_commands.describe(
        search="Search by item name",
        subteam="Filter by subteam",
        location="Filter by location"
    )
    async def view_inventory(
        self,
        interaction: discord.Interaction,
        search: Optional[str] = None,
        subteam: Optional[str] = None,
        location: Optional[str] = None
    ):
        await interaction.response.defer()

        items = await self.db.serach_items(search, subteam, location)

        if not items:
            await interaction.followup.send("No items found with your criteria")
            return

        view = InventoryPaginatedView(items, self.db)
        embed = view.create_embed(0)

        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="itemdetails", description="View detailed info about an item")
    @app_commands.describe(item_id="The item ID to view")
    async def item_details(self, interaction: discord.Interaction, item_id: int):
        await interaction.response.defer()

        item = await self.db.get_item(item_id)

        if not item:
            await interaction.followup.send("Item not found", ephemeral=True)
            return

        checkouts = await self.db.get_item_checkouts(item_id, active_only=True)

        embed = discord.Embed(
            title=item.item_name,
            color=discord.Color.blue(),
            timestamp=item.updated_at or item.created_at
        )

        embed.add_field(name="Item ID", value=str(item.id), inline=True)
        embed.add_field(name="Location", value=item.location, inline=True)
        embed.add_field(name="Subteam", value=item.subteam, inline=True)

        embed.add_field(
            name="Quantity",
            value=f"**Total:** {item.quantity_total}\n**Available:** {item.quantity_available}\n**Checked Out:** {item.quantity_checked_out}",
            inline=True
        )
        
        embed.add_field(name="Point of Contact", value=f"<@{item.point_of_contact}>", inline=True)

        if item.is_po_link:
            po_text = f"[View Thread]({item.purchase_order})"
        else:
            po_text = item.purchase_order
        embed.add_field(name="Purchase Order", value=po_text, inline=True)
        
        if item.description:
            embed.add_field(name="Description", value=item.description, inline=False)
        
        if checkouts:
            checkout_text = "\n".join([
                f"• <@{co.user_id}>: {co.quantity}x (since {co.checked_out_at.strftime('%b %d')})"
                for co in checkouts[:5]
            ])
            if len(checkouts) > 5:
                checkout_text += f"\n... and {len(checkouts) - 5} more"
            embed.add_field(name="Currently Checked Out To", value=checkout_text, inline=False)
        
        embed.set_footer(text=f"Last updated")
        
        view = ItemDetailsView(item, self.db)
        
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="edititem", description="Edit an existing item")
    @app_commands.describe(
        item_id="The item ID to edit",
        item_name="New name (optional)",
        quantity="New quantity (optional)",
        location="New location (optional)",
        subteam="New subteam (optional)",
        point_of_contact="New POC (optional)",
        purchase_order="New PO (optional)",
        description="New description (optional)"
    )
    async def edit_item(
        self,
        interaction: discord.Interaction,
        item_id: int,
        item_name: Optional[str] = None,
        quantity: Optional[int] = None,
        location: Optional[str] = None,
        subteam: Optional[str] = None,
        point_of_contact: Optional[discord.Member] = None,
        purchase_order: Optional[str] = None,
        description: Optional[str] = None
    ):
        await interaction.response.defer()

        item = await self.db.get_item(item_id)
        if not item:
            await interaction.followup.send("Item not found", ephemeral=True)
            return
        
        try:
            request = UpdateItemRequest(
                item_name=item_name,
                location=location,
                quantity_total=quantity,
                subteam=subteam,
                point_of_contact=point_of_contact.id if point_of_contact else None,
                purchase_order=purchase_order,
                description=description
            )

            if point_of_contact:
                await self.db.ensure_user_exists(point_of_contact.id, point_of_contact.name)
            
            updated_item = await self.db.update_item(item_id, request, interaction.user.id)

            if not updated_item:
                await interaction.followup.send("Failed to update item", ephemeral=True)
                return

            embed = discord.Embed(
                title="Item Updated",
                description=f"**{updated_item.item_name}** (ID: {updated_item.id})",
                color=discord.Color.green()
            )

            changes = []
            if item_name and item_name != item.item_name:
                changes.append(f"Name: {item.item_name} → {item_name}")
            if location and location != item.location:
                changes.append(f"Location: {item.location} → {location}")
            if quantity and quantity != item.quantity:
                changes.append(f"Quantity: {item.quantity} → {quantity}")
            if subteam and subteam != item.subteam:
                changes.append(f"Subteam: {item.subteam} → {subteam}")
            if point_of_contact and point_of_contact.id != item.point_of_contact:
                changes.append(f"POC: <@{item.point_of_contact}> → <@{point_of_contact.id}>")
            if purchase_order and purchase_order != item.purchase_order:
                changes.append(f"PO: {item.purchase_order} → {purchase_order}")
            
            if changes:
                embed.add_field(name="Changes", value="\n".join(changes), inline=False)
            
            embed.set_footer(text=f"Updated by {interaction.user.name}")
            
            await interaction.followup.send(embed=embed)

        except ValidationError as e:
            errors = "\n".join([f"• {err['loc'][0]}: {err['msg']}" for err in e.errors()])
            await interaction.followup.send(
                f"**Validation Error:**\n{errors}",
                ephemeral=True
            )
    @app_commands.command(name="deleteitem", description="Delete an item from inventory")
    @app_commands.describe(item_id="The item ID to delete")
    async def delete_item(self, interaction: discord.Interaction, item_id: int):
        await interaction.response.defer()

        item = await self.db.get_item(item_id)
        if not item:
            await interaction.followup.send("Item not found", ephemeral=True)
            return
        
        checkouts = await self.db.get_item_checkouts(item_id, active_only=True)
        if checkouts:
            await interaction.followup.send(
                "Cannot delete **{item.item_name}** - it has {len(checkouts)} active checkout(s)!\n"
                "Please return all items before deleting.",
                ephemeral=True
            )
            return
        
        view = DeleteConfirmationView(item, self.db, interaction.user.id)
        
        embed = discord.Embed(
            title="Confirm Deletion",
            description=f"Are you sure you want to delete **{item.item_name}**?",
            color=discord.Color.orange()
        )
        embed.add_field(name="Item ID", value=str(item.id), inline=True)
        embed.add_field(name="Quantity", value=str(item.quantity_total), inline=True)
        embed.add_field(name="Location", value=item.location, inline=True)
        
        await interaction.followup.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Inventory(bot, bot.db))
    