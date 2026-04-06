
import asyncio

import discord
from discord.ext import commands
import sqlite3
import os
from app.bot import Bot
from app.config import DISCORD_TOKEN, INIT_RETRY_DELAY_S, MAX_RETRY, RETRY_DELAY_S_MULTIPLIER
from app.utils.logger import logger
from app.web_server.web_server import start_web_server


async def main():
    global bot

    web_runner = await start_web_server()


    retry_delay = INIT_RETRY_DELAY_S
    current_retry = 0
    while current_retry < MAX_RETRY:
        current_retry += 1
        bot = Bot()
        try:
            # Blocking loop
            await bot.start(DISCORD_TOKEN) # type: ignore
        except discord.HTTPException as e:
            if e.status == 429:
                logger.warning(f"Rate limited. Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= RETRY_DELAY_S_MULTIPLIER;
            else:
                logger.warning(f"HTTP Error during bot startup: {e}")
                raise
        except Exception as e:
            logger.warning(f"Error during bot startup: {e}")
            raise
        finally:
            if not bot.is_closed():
                await bot.close()

    await web_runner.cleanup()

    logger.info("Initialization failed")


if __name__ == "__main__":
    asyncio.run(main())