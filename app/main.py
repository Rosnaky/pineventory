
import discord
from discord.ext import commands
import sqlite3
import os
from utils.logger import logger


def init():
    global bot

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='/', intents=intents)

    logger.info("Initialization successful")


if __name__ == "__main__":
    init()