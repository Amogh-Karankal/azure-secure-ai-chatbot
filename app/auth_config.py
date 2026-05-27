import os
from dotenv import load_dotenv

load_dotenv()

# Entra ID Configuration
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

# Scopes for Microsoft Graph
#SCOPE = ["User.Read", "User.Read.All", "Group.Read.All", "GroupMember.Read.All", "Directory.Read.All"]
SCOPE = ["User.Read", "User.ReadWrite.All", "Group.Read.All", "GroupMember.Read.All", "Directory.Read.All"]

# Redirect path (must match app registration)
REDIRECT_PATH = "/getAToken"

# Azure OpenAI Configuration
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# Flask Configuration
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

SERVICENOW_INSTANCE = "dev275801"
SERVICENOW_USER = "chatbot.integration"
SERVICENOW_PASSWORD = os.getenv("SERVICENOW_PASSWORD")