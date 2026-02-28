# Setup Guide

## Prerequisites

- Azure subscription
- Microsoft Entra ID tenant (Azure AD)
- Python 3.11+
- VS Code with Azure extension (for deployment)

## Phase 1: Azure OpenAI Setup

1. Create Azure OpenAI resource
2. Deploy GPT-4o model
3. Note endpoint URL

## Phase 2: Entra ID App Registration

1. Register application "Secure-AI-Chatbot"
2. Configure as single-tenant
3. Add redirect URIs:
   - `http://localhost:5000/getAToken` (local)
   - `https://your-app.azurewebsites.net/getAToken` (Azure)
4. Create client secret
5. Grant API permissions (User.Read)
6. Create app roles (ChatUser, ChatAdmin)

## Phase 3: Conditional Access Policy

1. Create policy "CA-AI-Chatbot-Require-MFA"
2. Target: Secure-AI-Chatbot application
3. Require: Multi-factor authentication
4. Enable policy

## Phase 4: Azure Key Vault

1. Create Key Vault
2. Add secrets:
   - CLIENT-ID
   - CLIENT-SECRET
   - TENANT-ID
   - FLASK-SECRET-KEY
3. Configure RBAC access

## Phase 5: Azure App Service

1. Create App Service (Python 3.11)
2. Enable system-assigned Managed Identity
3. Grant MI access to Key Vault (Key Vault Secrets User)
4. Grant MI access to OpenAI (Cognitive Services OpenAI User)
5. Configure environment variables:
   - KEY_VAULT_NAME
   - AZURE_OPENAI_ENDPOINT
   - AZURE_OPENAI_DEPLOYMENT
6. Enable HTTPS Only
7. Set startup command: `gunicorn --bind=0.0.0.0 --timeout 600 app:app`

## Phase 6: Deploy Code

1. Deploy via VS Code Azure extension
2. Or use ZIP deploy
3. Test the application

## Verification Checklist

- [ ] Login page loads
- [ ] Microsoft sign-in works
- [ ] MFA is prompted
- [ ] Chat responds with AI
- [ ] Audit logs are created
