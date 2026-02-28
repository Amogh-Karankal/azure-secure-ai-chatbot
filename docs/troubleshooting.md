# Troubleshooting Guide

## Common Issues

### 1. Redirect URI Mismatch (AADSTS50011)

**Error**: "The redirect URI specified in the request does not match"

**Fix**:
1. Go to App Registration → Authentication
2. Add the exact URI from the error message
3. Ensure it ends with `/getAToken`
4. Try in new incognito window

### 2. Key Vault Access Denied

**Error**: "Access denied to Key Vault"

**Fix**:
1. Go to Key Vault → Access control (IAM)
2. Add role assignment: "Key Vault Secrets User"
3. Assign to App Service's Managed Identity

### 3. OpenAI Access Denied

**Error**: "Cognitive Services access denied"

**Fix**:
1. Go to Azure OpenAI → Access control (IAM)
2. Add role assignment: "Cognitive Services OpenAI User"
3. Assign to App Service's Managed Identity

### 4. Container Timeout on Startup

**Error**: "Container did not start within expected time"

**Fix**:
1. Check startup command is correct
2. Restart the App Service
3. Check Log stream for errors

### 5. Deployment Not Found (404)

**Error**: "DeploymentNotFound" when chatting

**Fix**:
1. Verify AZURE_OPENAI_DEPLOYMENT matches your deployment name
2. Check deployment exists in Azure AI Foundry
3. Deployment names are case-sensitive

### 6. App Service Quota Exceeded

**Error**: "Error 403 - This web app is stopped"

**Fix**:
1. Free tier has daily quota limits
2. Upgrade to Basic B1 tier, or
3. Wait until next day (quota resets)

## Checking Logs

1. Go to App Service → Log stream
2. Watch real-time logs
3. Look for Python errors

## Testing Locally

If Azure deployment fails, test locally first:
```bash
# Activate virtual environment
source venv/bin/activate

# Run locally
python app.py

# Visit http://localhost:5000
```
