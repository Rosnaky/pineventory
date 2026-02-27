
import json

from app.config import GOOGLE_API_SCOPES
from google.oauth2.credentials import Credentials


def get_credentials():
    with open("google_token.json", 'r') as f:
        token_data = json.load(f)
    
    creds = Credentials.from_authorized_user_info(token_data, GOOGLE_API_SCOPES)
    
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        with open("google_token.json", 'w') as f:
            f.write(creds.to_json())
    
    return creds
