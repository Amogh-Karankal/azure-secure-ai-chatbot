# 🤖 Secure Azure AI Chatbot — IT Helpdesk Edition

An enterprise-grade AI chatbot built with Azure OpenAI (GPT-4o), secured with Microsoft Entra ID, Azure Key Vault, and Managed Identity — implementing Zero Trust security principles. Integrated with **Active Directory via Microsoft Graph API** and **ServiceNow via REST API** to serve as a full-stack IT Helpdesk assistant that can query, modify, and ticket across systems.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Azure OpenAI](https://img.shields.io/badge/Azure%20OpenAI-GPT--4o-orange?logo=openai)
![Entra ID](https://img.shields.io/badge/Microsoft%20Entra%20ID-Auth-blue?logo=microsoft)
![Key Vault](https://img.shields.io/badge/Azure%20Key%20Vault-Secrets-green?logo=microsoft-azure)
![Graph API](https://img.shields.io/badge/Microsoft%20Graph-API-purple?logo=microsoft)
![ServiceNow](https://img.shields.io/badge/ServiceNow-REST%20API-brightgreen?logo=servicenow)
![App Service](https://img.shields.io/badge/Azure%20App%20Service-Deployed-green?logo=microsoft-azure)
![License](https://img.shields.io/badge/License-MIT-green)

## 🎯 Project Overview

A production-ready AI application with enterprise security controls. The chatbot uses GPT-4o for intelligent conversations and acts as an automated IT helpdesk that can read/write to Active Directory and manage tickets through their full lifecycle in ServiceNow — all from natural language.

### Key Capabilities

**Active Directory Operations (via Microsoft Graph API):**
- Query user accounts, group memberships, account status, disabled accounts
- Reset passwords (auto-generated temp password, forces change on next sign-in)
- Disable/re-enable user accounts
- Detect on-prem synced accounts and advise to manage on the domain controller

**ServiceNow Ticket Lifecycle (via REST API):**
- Create incident tickets with caller, priority, impact, category, assignment group
- Look up ticket status by number
- Add work notes (auto-advances state from New to In Progress)
- Resolve tickets with resolution notes and resolution code
- Close tickets after user confirmation

**Multi-Step Automated Workflows:**
- Chain operations in one conversation (e.g., enable a disabled account, then reset its password)
- Full helpdesk flow from "user reports issue" to "ticket closed" — all conversationally

## 🏗️ Architecture



## 🔍 Integration Details

### AD Integration — Dual Token Architecture

Read operations use the signed-in user's **delegated token**, write operations use an **application token** via client credentials with a User Administrator directory role assigned to the service principal.

### ServiceNow Integration — REST API + Basic Auth

A dedicated `chatbot.integration` user in ServiceNow (with `itil` and `rest_api_explorer` roles, marked as Machine identity type and Internal Integration User) handles all API calls. Basic Auth with stored credentials. The integration is read-write — can create, query, update, and close incidents.

```
User: "Create a ticket for bruce.wayne — his printer isn't working. Medium urgency, Hardware"
  → create_servicenow_ticket() → INC0010003 created

User: "Add work note to INC0010003: cleared queue, restarting spooler"
  → add_work_note() → state auto-advances to In Progress

User: "Resolve INC0010003. Solution provided. Spooler restart fixed it. Confirmed with Bruce."
  → resolve_ticket() → state = Resolved

User: "Close INC0010003"
  → close_ticket() → state = Closed
```

### Supported Operations

| Operation | Example | Function | System |
|-----------|---------|----------|--------|
| User lookup | "Is john.smith enabled?" | `get_user_info` | AD |
| Group membership | "What groups is lisa.money in?" | `get_user_groups` | AD |
| Group members | "Members of Tier0-DomainAdmins?" | `get_group_members` | AD |
| All users | "List all users" | `list_all_users` | AD |
| All groups | "Show security groups" | `list_all_groups` | AD |
| Disabled accounts | "Any disabled accounts?" | `get_disabled_users` | AD |
| Password reset | "Reset alex.security's password" | `reset_user_password` | AD |
| Disable account | "Disable bob.wilson" | `disable_user_account` | AD |
| Enable account | "Enable alex.security" | `enable_user_account` | AD |
| Create ticket | "Open ticket for bruce.wayne, laptop issue" | `create_servicenow_ticket` | ServiceNow |
| Ticket status | "Status of INC0010001" | `get_ticket_status` | ServiceNow |
| Add work note | "Add note to INC0010001: ..." | `add_work_note` | ServiceNow |
| Resolve ticket | "Resolve INC0010001 — fixed via X" | `resolve_ticket` | ServiceNow |
| Close ticket | "Close INC0010001" | `close_ticket` | ServiceNow |

## 🔐 Security Controls

| Layer | Implementation |
|-------|---------------|
| **Authentication** | Microsoft Entra ID with MSAL |
| **MFA** | Conditional Access policy |
| **Secrets Management** | Azure Key Vault (Graph + ServiceNow credentials) |
| **Service Auth** | Managed Identity for Azure-to-Azure |
| **HTTPS Enforcement** | App Service HTTPS Only + ProxyFix middleware |
| **Security Headers** | X-Content-Type-Options, HSTS, X-Frame-Options, XSS Protection |
| **Graph Token Separation** | Delegated for reads, Application for writes |
| **ServiceNow Integration User** | Dedicated non-human account, scoped roles only |
| **Hybrid AD Awareness** | Blocks cloud writes on on-prem synced accounts |
| **Audit Logging** | Every login, query, and tool call logged |
| **Session Management** | Server-side Flask sessions |
| **CSRF Protection** | State parameter validation on OAuth callbacks |

## 🔗 Connected Environments

| System | Details |
|--------|---------|
| **On-Prem AD** | amoghlab.local on Oracle Cloud, Windows Server 2022, 15+ users, 8+ GPOs, LAPS, Tiered Admin Model — [Windows-AD-Lab](https://github.com/Amogh-Karankal/Windows-AD-Lab) |
| **Cloud AD** | Entra ID tenant synced via Entra Connect with Password Hash Sync |
| **ServiceNow** | Personal Developer Instance (Yokohama release), incident management module |

## 📁 Project Structure

```
azure-secure-ai-chatbot/
├── app/
│   ├── app.py                  # Main Flask app (ProxyFix, dual-token routing)
│   ├── auth_config.py          # Local config (Entra + ServiceNow creds)
│   ├── auth_config_azure.py    # Azure config (Key Vault + Managed Identity)
│   ├── graph_helpers.py        # AD operations + tool definitions
│   ├── servicenow_helpers.py   # ServiceNow ticket lifecycle operations
│   ├── requirements.txt
│   ├── templates/              # login.html, chat.html
│   └── static/                 # style.css
├── diagrams/
│   └── architecture.drawio
├── screenshots/
├── README.md
└── LICENSE
```

## 🚀 Deployment

### Prerequisites

- Azure subscription with App Service, OpenAI, Key Vault
- Microsoft Entra ID tenant with app registration
- On-premises AD synced via Entra Connect (for hybrid features)
- ServiceNow Personal Developer Instance with `chatbot.integration` user (roles: `itil`, `rest_api_explorer`)

### Local Development

```bash
git clone https://github.com/Amogh-Karankal/azure-secure-ai-chatbot.git
cd azure-secure-ai-chatbot/app

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Configure .env file
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
TENANT_ID=your-tenant-id
FLASK_SECRET_KEY=your-secret-key
AZURE_OPENAI_KEY=your-openai-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
SERVICENOW_PASSWORD=your-servicenow-integration-password

python app.py
```

### Azure App Service Deployment

1. Create App Service (Python 3.11), enable system-assigned Managed Identity
2. Create Azure Key Vault, store secrets including `SERVICENOW-PASSWORD`
3. Grant Managed Identity Key Vault Secrets User role
4. Grant Managed Identity Cognitive Services OpenAI User role
5. Configure App Service env vars: `KEY_VAULT_NAME`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `SERVICENOW_INSTANCE`, `SERVICENOW_USER`
6. Set startup command: `gunicorn --bind=0.0.0.0 --timeout 600 app:app`
7. Enable HTTPS Only
8. Add redirect URI to Entra app: `https://your-app.azurewebsites.net/getAToken`
9. Grant admin consent for Graph permissions (Delegated + Application)
10. Assign User Administrator role to the app's service principal
11. Deploy code via Kudu SSH or VS Code

### Troubleshooting

| Issue | Fix |
|-------|-----|
| Redirect URI mismatch | Verify both `localhost` and App Service URL added to app registration |
| `http://` instead of `https://` | ProxyFix middleware handles this — ensure updated `app.py` is deployed |
| Password reset returns 403 | Assign User Administrator role to app service principal |
| ServiceNow API 401 | Verify `chatbot.integration` user has `itil` and `rest_api_explorer` roles |
| ServiceNow Resolution code rejected | Use valid Yokohama values: 'Solution provided', 'Workaround provided', etc. |
| ServiceNow PDI hibernated | Log into developer.servicenow.com to wake it (5-10 min) |
| On-prem account can't be modified | Expected — synced accounts must be managed on the DC |

## 🛠️ Technologies

| Category | Technology |
|----------|-----------|
| **AI** | Azure OpenAI (GPT-4o), Function Calling (14 tools) |
| **Backend** | Python, Flask, Gunicorn |
| **Authentication** | Microsoft Entra ID, MSAL, Conditional Access |
| **AD Integration** | Microsoft Graph API, Entra Connect |
| **Ticketing** | ServiceNow REST API (Yokohama) |
| **Token Architecture** | Delegated (reads) + Application (writes) for Graph; Basic Auth for ServiceNow |
| **Secrets** | Azure Key Vault, Managed Identity |
| **Hosting** | Azure App Service (B1) |
| **Proxy** | Werkzeug ProxyFix |
| **Logging** | Python logging module |

## 📈 Future Enhancements

- Role-based access in chatbot (only IT_Admins can run write operations)
- Auto-create ServiceNow ticket when password reset is performed (audit trail)
- Azure Content Safety integration
- RAG with IT knowledge base articles
- Markdown rendering in chat
- ServiceNow Service Catalog item integration

## 🔗 Related Projects

- **[Windows AD Lab](https://github.com/Amogh-Karankal/Windows-AD-Lab)** — On-prem AD environment synced to this chatbot

## 👤 Author

**Amogh Karankal**

- GitHub: [@Amogh-Karankal](https://github.com/Amogh-Karankal)
- LinkedIn: [Amogh Karankal](https://www.linkedin.com/in/amoghkarankal/)

## 📄 License

MIT License

---

*Built as part of IT helpdesk and cybersecurity career development*
