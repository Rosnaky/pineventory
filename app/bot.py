# bot.py
import discord
from discord.ext import commands
import asyncio
from app.config import *
from app.db.db_manager import DatabaseManager
from app.db.migrations.migrate import MigrationManager
from app.sheets.sheets_manager import SheetsManager
from app.utils.logger import logger

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents)
        self.sheets = SheetsManager()
        self.db = DatabaseManager(DB_URL) # type: ignore
    
    async def setup_hook(self):
        await self.db.connect()
        
        if GOOGLE_SERVICE_ACCOUNT_FILE:
            connected = self.sheets.connect()
            if connected:
                self.db.set_sheets_manager(self.sheets)

        logger.info("Running database migrations...")
        migrator = MigrationManager(DB_URL) # type: ignore
        await migrator.run_migrations()
        
        await self.load_extension('app.cogs.inventory')
        await self.load_extension('app.cogs.checkout')
        await self.load_extension('app.cogs.admin')
        
        # Sync slash commands
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Synced commands to guild {GUILD_ID}")
        else:
            await self.tree.sync()
            logger.info("Synced commands globally")
    
    async def on_ready(self):
        logger.info(f'🤖 {self.user} is online!')

        await self.setup_sheets_for_existing_guilds()

        await self.change_presence(activity=discord.Game(name=STATUS_MESSAGE))

    async def setup_sheets_for_existing_guilds(self):
        if not self.sheets.client:
            return
        
        logger.info("Checking for guilds without spreadsheets.")
        for guild in self.guilds:
            settings = await self.db.get_guild_settings(guild.id)
            
            if not settings or not settings.google_sheet_id:
                await self.create_sheet_for_guild(guild)

    async def on_guild_join(self, guild: discord.Guild):
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")

        await self.db.upsert_guild_settings(guild.id, guild.name)

        if self.sheets.client:
            await self.create_sheet_for_guild(guild)

    async def create_sheet_for_guild(self, guild: discord.Guild):
        try:
            sheet_id, sheet_url = await self.sheets.create_sheet_for_guild(
                guild.id,
                guild.name
            )
            
            await self.db.set_guild_sheet(guild.id, sheet_id, sheet_url)
            
            spreadsheet = await self.sheets.get_sheet_for_guild(guild.id, sheet_id)
            if spreadsheet:
                await self.sheets.make_sheet_public(spreadsheet)
                logger.info(f"Sheet for {guild.name} is now publicly viewable")
            
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    embed = discord.Embed(
                        title="Inventory Tracking Sheet Created!",
                        description="A Google Sheet has been created to track this server's inventory.",
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="View Your Inventory",
                        value=f"[Click here to view the sheet]({sheet_url})",
                        inline=False
                    )
                    embed.add_field(
                        name="Auto-Sync",
                        value="The sheet automatically updates when you add items, check out equipment, etc.",
                        inline=False
                    )
                    embed.add_field(
                        name="Commands",
                        value="• `/sheetinfo` - View sheet link\n• `/syncsheets` - Manually sync data",
                        inline=False
                    )
                    
                    await channel.send(embed=embed)
                    break
            
            logger.info(f"Google Sheet created for {guild.name}: {sheet_url}")
            
        except Exception as e:
            logger.error(f"Failed to create sheet for {guild.name}: {e}")

    async def on_guild_remove(self, guild: discord.Guild):
        logger.info(f"Left guild: {guild.name} (ID: {guild.id})")

    async def close(self):
        await self.db.close()
        await super().close()
