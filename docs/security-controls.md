# Security Controls

## Authentication & Authorization

### Entra ID Integration
- OAuth 2.0 Authorization Code Flow with PKCE
- OpenID Connect for identity tokens
- Single-tenant application (organization only)

### Conditional Access Policy
- **Name**: CA-AI-Chatbot-Require-MFA
- **Target**: Secure-AI-Chatbot application
- **Requirement**: Multi-factor authentication
- **Result**: Users must complete MFA to access the app

### App Roles
| Role | Permission |
|------|------------|
| ChatUser | Basic chat access |
| ChatAdmin | Chat + admin features |

## Secrets Management

### Azure Key Vault
All sensitive configuration stored in Key Vault:

| Secret | Purpose |
|--------|---------|
| CLIENT-ID | Entra ID app identifier |
| CLIENT-SECRET | App authentication |
| TENANT-ID | Directory identifier |
| FLASK-SECRET-KEY | Session encryption |

### Access Control
- Managed Identity has "Key Vault Secrets User" role
- No secrets in code or environment variables
- Secrets retrieved at runtime

## Managed Identity

### How It Works
1. App Service has system-assigned identity
2. Identity granted RBAC roles on Azure resources
3. App requests token using identity (no credentials)
4. Token used to access Key Vault and OpenAI

### Roles Assigned
| Resource | Role |
|----------|------|
| Key Vault | Key Vault Secrets User |
| Azure OpenAI | Cognitive Services OpenAI User |

## Network Security

### HTTPS Enforcement
- HTTP requests redirected to HTTPS
- HSTS header with 1-year max-age
- Automatic SSL certificate from Azure

### Security Headers
```python
response.headers['X-Content-Type-Options'] = 'nosniff'
response.headers['X-Frame-Options'] = 'DENY'
response.headers['X-XSS-Protection'] = '1; mode=block'
response.headers['Strict-Transport-Security'] = 'max-age=31536000'
response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
```

## Audit Logging

### What's Logged
- Login success/failure with username and timestamp
- Chat inputs (first 100 characters)
- Chat outputs (first 100 characters)
- Logout events
- Error events

### Log Format
```
2026-02-26 10:15:30 - INFO - LOGIN SUCCESS - User: user@domain.com
2026-02-26 10:15:45 - INFO - CHAT INPUT - User: user@domain.com - Message: Hello...
2026-02-26 10:15:47 - INFO - CHAT OUTPUT - User: user@domain.com - Response: Hi there...
```
## Zero Trust Checklist

- [x] Verify explicitly — Every request authenticated
- [x] Least privilege — Minimal permissions granted
- [x] Assume breach — Comprehensive logging enabled
- [x] Encrypt in transit — HTTPS enforced
- [x] No hardcoded secrets — Key Vault used
- [x] No API keys — Managed Identity used
