import os
from dotenv import load_dotenv

load_dotenv()

# Secrets
DB_URL = os.getenv("DB_URL")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

# User interface
STATUS_MESSAGE = "There will be a day that I will be used for the last time. Scary."
COMMAND_PREFIX = "!"

# Google Services
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
GOOGLE_SHEETS_FOLDER_ID = os.getenv("GOOGLE_SHEETS_FOLDER_ID")
GOOGLE_API_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
GOOGLE_TOKEN_FILE = "google_token.json"
GOOGLE_CREDS_FILE = "oauth_creds.json"

# Web server
WEB_SERVER_PORT=8080