
import asyncio

import discord
from discord.ext import commands
import sqlite3
import os
from app.bot import Bot
from app.config import DISCORD_TOKEN
from app.utils.logger import logger
from app.web_server.web_server import start_web_server


async def main():
    global bot

    web_runner = await start_web_server()

    bot = Bot()
    try:
        await bot.start(DISCORD_TOKEN) # type: ignore
    finally:
        await web_runner.cleanup()

    logger.info("Initialization successful")


if __name__ == "__main__":
    asyncio.run(main())