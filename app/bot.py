# bot.py
import discord
from discord.ext import commands
import asyncio
from app.config import *
from app.db.db_manager import DatabaseManager
from app.db.migrations.migrate import MigrationManager

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True  # For member mentions
        
        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents)
        self.db = DatabaseManager(DB_URL)
    
    async def setup_hook(self):
        await self.db.connect()
        
        print("Running database migrations...")
        migrator = MigrationManager(DB_URL)
        await migrator.run_migrations()
        
        await self.load_extension('app.cogs.inventory')
        await self.load_extension('app.cogs.checkout')
        
        # Sync slash commands
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"Synced commands to guild {GUILD_ID}")
        else:
            await self.tree.sync()
            print("Synced commands globally")
    
    async def on_ready(self):
        print(f'🤖 {self.user} is online!')
        await self.change_presence(activity=discord.Game(name=STATUS_MESSAGE))
    
    async def close(self):
        await self.db.close()
        await super().close()
