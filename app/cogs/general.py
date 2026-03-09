import discord
from discord import app_commands
from discord.ext import commands

from app.bot import Bot
from app.db.db_manager import DatabaseManager

class General(commands.Cog):
    def __init__(self, bot: Bot, db_manager: DatabaseManager):
        self.bot: Bot = bot
        self.db: DatabaseManager = db_manager
        
    @app_commands.command(name="about", description="Learn about Pineventory")
    async def about(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Pineventory",
            description="A Discord bot for managing your team's physical inventory. Track equipment, checkouts, and returns — all from Discord.",
            color=discord.Color.green(),
        )

        embed.add_field(
            name="Getting Started",
            value=(
                "`/additem` — Add items to your inventory\n"
                "`/inventory` — Browse all items\n"
                "`/itemdetails` — View a specific item\n"
                "`/checkout` — Check out an item\n"
                "`/mycheckouts` — View your active checkouts\n"
                "`/sheetinfo` — View your server's linked sheet"
            ),
            inline=False,
        )

        embed.add_field(
            name="Admin Commands",
            value=(
                "`/setadmin` — Grant or revoke bot admin\n"
                "`/syncsheets` — Sync inventory to Google Sheets"
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pineventory", description="Sounds like you need inventory management slime!")
    async def pineventory(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Sounds like you need Pineventory!",
            description=(
                "Stop losing track of your team's equipment. "
                "Pineventory lets you manage your entire inventory right here in Discord - "
                "you feel me?"
            ),
            color=discord.Color.green(),
        )

        embed.add_field(
            name="What it does",
            value=(
                "Track items, check out equipment, log returns, "
                "and keep everyone on the same page with automatic Google Sheets sync."
            ),
            inline=False,
        )

        embed.add_field(
            name="Get started",
            value="Run `/about` to see all available commands.",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

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

async def setup(bot):
    await bot.add_cog(General(bot, bot.db))
