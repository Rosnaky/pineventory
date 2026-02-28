# app/cogs/admin.py
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
from app.db.db_manager import DatabaseManager
from app.utils.logger import logger

class Admin(commands.Cog):
    def __init__(self, bot, db_manager: DatabaseManager):
        self.bot = bot
        self.db: DatabaseManager = db_manager

    # TODO: Fix
    async def interaction_check(self, interaction: discord.Interaction) -> bool:  # type: ignore[override]        
        if not isinstance(interaction.user, discord.Member):
            return False
        
        if interaction.permissions.administrator:
            return True
        
        if not interaction.guild_id:
            return False

        is_admin = await self.db.is_admin(interaction.guild_id, interaction.user.id)
        
        if not is_admin:
            await interaction.response.send_message(
                "You need administrator permissions to use this command.", 
                ephemeral=True
            )

        return is_admin
    
    @app_commands.command(name="setadmin", description="Grant or revoke admin permissions")
    @app_commands.describe(
        user="User to modify",
        admin="True to grant admin, False to revoke"
    )
    async def set_admin(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        admin: bool
    ):
        guild_id = interaction.guild_id

        if not guild_id:
            await interaction.response.send_message(
                "Could not detect server.", 
                ephemeral=True
            )
            return
        
        await self.db.ensure_guild_member(guild_id, interaction.user.id, interaction.user.name)
        await self.db.ensure_guild_member(guild_id, user.id, user.name)

        if user.guild_permissions.administrator and not admin:
            await interaction.response.send_message(
                "You can not revoke admin from a server admin.", 
                ephemeral=True
            )
            return

        await self.db.set_admin(guild_id, user.id, admin)

        embed = discord.Embed(
            title="Admin Permissions Updated",
            color=discord.Color.green()
        )
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(
            name="Admin Status",
            value="Admin" if admin else "Not Admin",
            inline=True
        )
        embed.set_footer(text=f"Updated by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="listadmins", description="List all admins in this server")
    async def list_admins(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        
        if not guild_id:
            await interaction.response.send_message(
                "Could not detect server.", 
                ephemeral=True
            )
            return
        
        if not isinstance(interaction.guild, discord.Guild):
            await interaction.response.send_message(
                "This can only be used in a server.", 
                ephemeral=True
            )
            return

        admins = await self.db.get_guild_admins(guild_id)
        
        if not admins:
            await interaction.response.send_message(
                "No bot admins set for this server. Server administrators can use `/setadmin` to add admins.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"Bot Admins for {interaction.guild.name}",
            color=discord.Color.blue(),
            description=f"Total: {len(admins)} admin(s)"
        )
        
        admin_list = "\n".join([f"• <@{admin.user_id}>" for admin in admins])
        
        embed.add_field(name="Admins", value=admin_list, inline=False)
        embed.set_footer(text="Note: Discord server administrators also have bot admin access")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="checkadmin", description="Check if a user is an admin")
    @app_commands.describe(user="User to check (leave empty to check yourself)")
    async def check_admin(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        target_user = user or interaction.user
        guild_id = interaction.guild_id
        
        if not isinstance(target_user, discord.Member):
            await interaction.response.send_message(
                "This command can only be used by Discord members.",
                ephemeral=True
            )
            return 
        
        if not guild_id:
            await interaction.response.send_message(
                "This command can only be used in servers.",
                ephemeral=True
            )
            return
        
        is_discord_admin = target_user.guild_permissions.administrator
        is_bot_admin = await self.db.is_admin(guild_id, target_user.id)
        
        embed = discord.Embed(
            title=f"🔍 Admin Status: {target_user.name}",
            color=discord.Color.green() if (is_discord_admin or is_bot_admin) else discord.Color.red()
        )
        
        embed.add_field(
            name="Discord Administrator",
            value="Yes" if is_discord_admin else "No",
            inline=True
        )
        embed.add_field(
            name="Bot Admin",
            value="Yes" if is_bot_admin else "No",
            inline=True
        )
        embed.add_field(
            name="Can Use Admin Commands",
            value="Yes" if (is_discord_admin or is_bot_admin) else "No",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="sheetinfo", description="Get info about this server's Google Sheet")
    async def sheet_info(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id

        if not guild_id or not isinstance(interaction.guild, discord.Guild):
            await interaction.response.send_message(
                "This command can only be used in servers.",
                ephemeral=True
            )
            return
        
        settings = await self.db.get_guild_settings(guild_id)
        
        if not settings or not settings.google_sheet_id:
            await interaction.response.send_message(
                "No Google Sheet has been created for this server yet!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"Inventory Sheet for {interaction.guild.name}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Sheet URL",
            value=f"[Click to view]({settings.google_sheet_url})",
            inline=False
        )
        
        embed.add_field(
            name="Auto-Sync",
            value="Enabled - Updates automatically on changes",
            inline=True
        )
        
        embed.add_field(
            name="Public Access",
            value="Anyone with the link can view (read-only)",
            inline=True
        )
        
        embed.add_field(
            name="Manual Sync",
            value="Use `/syncsheets` to force an update",
            inline=False
        )
        
        if settings.updated_at:
            embed.set_footer(text=f"Last updated: {settings.updated_at.strftime('%Y-%m-%d %H:%M')}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="syncsheets", description="Manually sync inventory to Google Sheets")
    async def sync_sheets(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        if not self.bot.sheets.client:
            await interaction.followup.send(
                "Google Sheets is not configured!",
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild_id

        if not guild_id or not isinstance(interaction.guild, discord.Guild):
            await interaction.followup.send(
                "This command can only be used in servers.",
                ephemeral=True
            )
            return
        
        settings = await self.db.get_guild_settings(guild_id)
        if not settings or not settings.google_sheet_id:
            await interaction.followup.send(
                "No Google Sheet found for this server!",
                ephemeral=True
            )
            return
        
        await self.bot.sheets.full_sync(self.db, guild_id)
        
        embed = discord.Embed(
            title="Google Sheet Synced",
            description="Inventory data has been updated",
            color=discord.Color.green()
        )
        embed.add_field(
            name="View Sheet",
            value=f"[Click here]({settings.google_sheet_url})",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Admin(bot, bot.db))
