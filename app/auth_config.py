import os
from dotenv import load_dotenv

load_dotenv()

# Entra ID Configuration
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

# Scopes for Microsoft Graph
SCOPE = ["User.Read"]

# Redirect path (must match app registration)
REDIRECT_PATH = "/getAToken"

# Azure OpenAI Configuration
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# Flask Configuration
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")