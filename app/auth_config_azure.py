import os
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient

# Check if running in Azure or locally
RUNNING_IN_AZURE = os.getenv("WEBSITE_HOSTNAME") is not None

# Key Vault configuration
KEY_VAULT_NAME = os.getenv("KEY_VAULT_NAME")

def get_secret(secret_name):
    """Retrieve secret from Key Vault or environment variable"""
    if RUNNING_IN_AZURE and KEY_VAULT_NAME:
        try:
            key_vault_uri = f"https://{KEY_VAULT_NAME}.vault.azure.net/"
            credential = ManagedIdentityCredential()
            client = SecretClient(vault_url=key_vault_uri, credential=credential)
            secret = client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            print(f"Key Vault error: {e}")
            return None
    else:
        # Local development - use environment variables
        env_name = secret_name.replace("-", "_").upper()
        return os.getenv(env_name)

# Load configuration
CLIENT_ID = get_secret("CLIENT-ID")
CLIENT_SECRET = get_secret("CLIENT-SECRET")
TENANT_ID = get_secret("TENANT-ID")
FLASK_SECRET_KEY = get_secret("FLASK-SECRET-KEY") or "dev-secret-key"

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["User.Read"]
REDIRECT_PATH = "/getAToken"

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")  # For local dev fallback