
import discord

from app.utils.logger import logger


class MyCheckoutsView(discord.ui.View):
    def __init__(self, checkouts, db_manager):
        super().__init__(timeout=300)
        self.checkouts = checkouts
        self.db = db_manager
        
        if checkouts:
            self.add_item(ReturnButton(checkouts[0]))

class ReturnButton(discord.ui.Button):
    def __init__(self, checkout):
        super().__init__(
            label=f"Return Checkout #{checkout.id}",
            style=discord.ButtonStyle.green,
            custom_id=f"return_{checkout.id}"
        )
        self.checkout = checkout
    
    async def callback(self, interaction: discord.Interaction):
        if not self.view:
            logger.error("No view found in Return Button")
            return
        
        if not interaction.guild_id:
            await interaction.response.send_message(
                "This command must be used in a server.",
                ephemeral=True
            )
            return
        
        db = self.view.db
        success = await db.return_item(self.checkout.id, interaction.guild_id, interaction.user.id)
        
        if success:
            await interaction.response.send_message(
                f"Returned checkout #{self.checkout.id}",
                ephemeral=True
            )
            
            checkouts = await db.get_active_checkouts(interaction.user.id)
            
        else:
            await interaction.response.send_message(
                "Failed to return item",
                ephemeral=True
            )