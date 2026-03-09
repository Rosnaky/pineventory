import discord
from typing import Dict, List

from app.db.models import Checkout

class AllCheckoutsView(discord.ui.View):
    def __init__(self, user_checkouts: Dict[int, List[Checkout]], items_by_id: dict, guild: discord.Guild):
        super().__init__(timeout=300)
        self.user_checkouts = user_checkouts
        self.items_by_id = items_by_id
        self.guild = guild
        self.current_filter = "all"
        self.current_page = 0
        self.per_page = 5
        
        self._build_user_select()
        self._update_pagination()

    def _build_user_select(self):
        options = [
            discord.SelectOption(
                label="All Users",
                description=f"{sum(len(cos) for cos in self.user_checkouts.values())} total checkouts",
                value="all",
                default=self.current_filter == "all"
            )
        ]
        
        for user_id, checkouts in list(self.user_checkouts.items())[:24]:
            user = self.guild.get_member(user_id)
            user_name = user.display_name if user else f"User {user_id}"
            
            options.append(discord.SelectOption(
                label=user_name[:100],
                description=f"{len(checkouts)} checkout(s)",
                value=str(user_id),
                default=self.current_filter == str(user_id)
            ))
        
        self.user_select.options = options

    def _update_pagination(self):
        if self.current_filter == "all":
            max_pages = 1
        else:
            user_id = int(self.current_filter)
            checkouts = self.user_checkouts.get(user_id, [])
            max_pages = max((len(checkouts) - 1) // self.per_page + 1, 1)
        
        self.max_pages = max_pages
        self.previous_button.disabled = self.current_page == 0 or max_pages <= 1
        self.next_button.disabled = self.current_page >= max_pages - 1 or max_pages <= 1

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Active Checkouts",
            color=discord.Color.blue()
        )
        
        if self.current_filter == "all":
            total_checkouts = sum(len(cos) for cos in self.user_checkouts.values())
            embed.description = f"**Total:** {total_checkouts} active checkout{'s' if total_checkouts != 1 else ''}"
            
            for user_id, user_cos in list(self.user_checkouts.items())[:10]:
                user = self.guild.get_member(user_id)
                user_display = user.display_name if user else f"User {user_id}"
                
                items_text = []
                for co in user_cos[:5]:
                    item_name = self.items_by_id.get(co.item_id, "Unknown")
                    overdue_tag = " [OVERDUE]" if co.is_overdue else ""
                    items_text.append(f"• {item_name} — {co.quantity}x{overdue_tag}")
                
                if len(user_cos) > 5:
                    items_text.append(f"• _...and {len(user_cos) - 5} more_")
                
                embed.add_field(
                    name=user_display,
                    value="\n".join(items_text) if items_text else "_No active checkouts_",
                    inline=False
                )
            
            if len(self.user_checkouts) > 10:
                embed.set_footer(text=f"Showing 10 of {len(self.user_checkouts)} users")
        else:
            user_id = int(self.current_filter)
            user = self.guild.get_member(user_id)
            user_display = user.display_name if user else f"User {user_id}"
            
            user_cos = self.user_checkouts.get(user_id, [])
            start = self.current_page * self.per_page
            page_checkouts = user_cos[start : start + self.per_page]
            
            total = len(user_cos)
            embed.description = f"**{user_display}** — {total} checkout{'s' if total != 1 else ''}"
            
            for co in page_checkouts:
                item_name = self.items_by_id.get(co.item_id, "Unknown")
                
                lines = [
                    f"**Quantity:** {co.quantity}x",
                    f"**Checked out:** <t:{int(co.checked_out_at.timestamp())}:R>",
                ]
                
                if co.expected_return_date:
                    lines.append(f"**Expected return:** <t:{int(co.expected_return_date.timestamp())}:D>")
                    if co.is_overdue:
                        lines.append("**Status:** OVERDUE")
                
                if co.notes:
                    lines.append(f"**Notes:** _{co.notes[:80]}_")
                
                embed.add_field(
                    name=f"{item_name} (Checkout #{co.id})",
                    value="\n".join(lines),
                    inline=False,
                )
            
            if self.max_pages > 1:
                embed.set_footer(text=f"Page {self.current_page + 1} of {self.max_pages}")
        
        return embed

    @discord.ui.select(
        placeholder="Filter by user...",
        options=[discord.SelectOption(label="placeholder", value="0")],
        row=0
    )
    async def user_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.current_filter = select.values[0]
        self.current_page = 0
        
        self._build_user_select()
        self._update_pagination()
        
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, row=1)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_pagination()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=1)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self._update_pagination()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()
