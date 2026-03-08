import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from app.config import *

def get_credentials():
    creds = None
    
    if os.path.exists(GOOGLE_TOKEN_FILE):
        with open(GOOGLE_TOKEN_FILE, 'r') as f:
            creds_data = json.load(f)
            creds = Credentials.from_authorized_user_info(creds_data, GOOGLE_API_SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired Google token...")
            creds.refresh(Request())
        else:
            print("Please authenticate with Google...")
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDS_FILE, GOOGLE_API_SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(GOOGLE_TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
        print("Google credentials saved!")
    
    return creds