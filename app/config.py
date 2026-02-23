import os
from dotenv import load_dotenv

load_dotenv()

# Secrets
DB_URL = os.getenv("DB_URL")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

# User interface
STATUS_MESSAGE = "Pineventory ready!"
COMMAND_PREFIX = "!"
