
import asyncio

import discord
from discord.ext import commands
import sqlite3
import os
from app.bot import Bot
from app.config import DISCORD_TOKEN
from app.utils.logger import logger


async def main():
    global bot

    bot = Bot()
    async with bot:
        await bot.start(DISCORD_TOKEN)


    logger.info("Initialization successful")


if __name__ == "__main__":
    asyncio.run(main())