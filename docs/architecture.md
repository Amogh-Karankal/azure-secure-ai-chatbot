# Architecture Overview

## System Components

### 1. User Interface
- **Login Page**: Microsoft-branded sign-in button
- **Chat Interface**: Real-time AI conversation
- **Responsive Design**: Works on desktop and mobile

### 2. Azure App Service
- **Runtime**: Python 3.11 with Flask
- **Hosting**: Linux container
- **Scaling**: Basic B1 tier (can scale up)
- **HTTPS**: Automatic SSL certificate

### 3. Microsoft Entra ID
- **Authentication**: OAuth 2.0 / OpenID Connect
- **MFA**: Enforced via Conditional Access
- **App Registration**: Single-tenant application
- **Permissions**: User.Read (minimal scope)

### 4. Azure Key Vault
- **Secrets Stored**:
  - CLIENT-ID
  - CLIENT-SECRET
  - TENANT-ID
  - FLASK-SECRET-KEY
- **Access**: RBAC with Managed Identity

### 5. Azure OpenAI
- **Model**: GPT-4o
- **Access**: Managed Identity (no API key)
- **Use**: Chat completions API

## Data Flow

1. User visits app URL
2. App redirects to Microsoft login
3. User authenticates + completes MFA
4. Microsoft returns token to app
5. App validates token, creates session
6. User sends chat message
7. App retrieves secrets from Key Vault
8. App calls Azure OpenAI with Managed Identity
9. AI response returned to user
10. All actions logged for audit

## Security Boundaries
```
┌─────────────────────────────────────────────────────────┐
│                    INTERNET                             │
└─────────────────────────┬───────────────────────────────┘
│ HTTPS Only
┌─────────────────────────▼───────────────────────────────┐
│                 AZURE APP SERVICE                       │
│  ┌─────────────────────────────────────────────────┐    │
│  │              APPLICATION CODE                   │    │
│  │  • Token validation on every request            │    │
│  │  • Session management                           │    │
│  │  • Security headers                             │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────┬───────────────────────────────┘
│ Managed Identity
┌─────────────────┼─────────────────┐
▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   KEY VAULT   │ │ AZURE OPENAI  │ │   ENTRA ID    │
│  (Secrets)    │ │   (AI API)    │ │   (Auth)      │
└───────────────┘ └───────────────┘ └───────────────┘
```

