import discord


class DeleteConfirmationView(discord.ui.View):
    def __init__(self, item, db_manager, user_id):
        super().__init__(timeout=60)
        self.item = item
        self.db = db_manager
        self.user_id = user_id
    
    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your deletion request!", ephemeral=True)
            return
        
        success = await self.db.delete_item(self.item.id, interaction.user.id)
        
        if success:
            await interaction.response.edit_message(
                content=f"Deleted **{self.item.item_name}** (ID: {self.item.id})",
                embed=None,
                view=None
            )
        else:
            await interaction.response.edit_message(
                content="Failed to delete item",
                embed=None,
                view=None
            )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your deletion request!", ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content="Deletion cancelled.",
            embed=None,
            view=None
        )
