
import discord
class InventoryPaginatedView(discord.ui.View):
    def __init__(self, items, db_manager):
        super().__init__(timeout=300)
        self.items = items
        self.db = db_manager
        self.current_page = 0
        self.items_per_page = 5
        self.max_pages = (len(items) - 1) // self.items_per_page + 1
        
        if self.max_pages == 1:
            self.previous_button.disabled = True
            self.next_button.disabled = True
    
    def create_embed(self, page):
        start = page * self.items_per_page
        end = start + self.items_per_page
        page_items = self.items[start:end]
        
        embed = discord.Embed(
            title="📦 Inventory",
            color=discord.Color.blue(),
            description=f"Showing {start + 1}-{min(end, len(self.items))} of {len(self.items)} items"
        )
        
        for item in page_items:
            availability = f"{item.quantity_available}/{item.quantity_total}"
            if item.quantity_checked_out > 0:
                availability += f" ({item.quantity_checked_out} checked out)"
            
            field_value = f"**ID:** {item.id}\n"
            field_value += f"**Location:** {item.location}\n"
            field_value += f"**Subteam:** {item.subteam}\n"
            field_value += f"**Available:** {availability}\n"
            field_value += f"**POC:** <@{item.point_of_contact}>"
            
            embed.add_field(
                name=item.item_name,
                value=field_value,
                inline=False
            )
        
        embed.set_footer(text=f"Page {page + 1}/{self.max_pages}")
        return embed
    
    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            
            self.previous_button.disabled = (self.current_page == 0)
            self.next_button.disabled = False
            
            embed = self.create_embed(self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            
            self.next_button.disabled = (self.current_page == self.max_pages - 1)
            self.previous_button.disabled = False
            
            embed = self.create_embed(self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
