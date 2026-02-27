import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

flow = InstalledAppFlow.from_client_secrets_file("oauth_creds.json", SCOPES)
creds = flow.run_local_server(port=0)

# Save the token for reuse
with open("google_token.json", 'w') as f:
    f.write(creds.to_json())

# Test it
client = gspread.authorize(creds)
sheet = client.create("Test Sheet")
print(f"Created: {sheet.url}")
