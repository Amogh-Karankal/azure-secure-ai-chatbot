# 🤖 Secure Azure AI Chatbot — IT Helpdesk Edition

An enterprise-grade AI chatbot built with Azure OpenAI (GPT-4o), secured with Microsoft Entra ID, Azure Key Vault, and Managed Identity — implementing Zero Trust security principles. Integrated with **Active Directory via Microsoft Graph API** and **ServiceNow via REST API**, with **role-based access control** gating privileged operations. A full-stack IT Helpdesk assistant that queries, modifies, and tickets across systems — with authorization enforced by AD group membership.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Azure OpenAI](https://img.shields.io/badge/Azure%20OpenAI-GPT--4o-orange?logo=openai)
![Entra ID](https://img.shields.io/badge/Microsoft%20Entra%20ID-Auth-blue?logo=microsoft)
![Key Vault](https://img.shields.io/badge/Azure%20Key%20Vault-Secrets-green?logo=microsoft-azure)
![Graph API](https://img.shields.io/badge/Microsoft%20Graph-API-purple?logo=microsoft)
![ServiceNow](https://img.shields.io/badge/ServiceNow-REST%20API-brightgreen?logo=servicenow)
![RBAC](https://img.shields.io/badge/RBAC-Group%20Based-red)
![App Service](https://img.shields.io/badge/Azure%20App%20Service-Deployed-green?logo=microsoft-azure)
![License](https://img.shields.io/badge/License-MIT-green)

## 🎯 Project Overview

A production-ready AI application with enterprise security controls. The chatbot uses GPT-4o for intelligent conversations and acts as an automated IT helpdesk that can read/write to Active Directory and manage tickets through their full lifecycle in ServiceNow — all from natural language, with privileged operations protected by role-based access control.

### Key Capabilities

**Active Directory Operations (via Microsoft Graph API):**
- Query user accounts, group memberships, account status, disabled accounts
- Reset passwords (auto-generated temp password, forces change on next sign-in) — *admin only*
- Disable/re-enable user accounts — *admin only*
- Detect on-prem synced accounts and advise to manage on the domain controller

**ServiceNow Ticket Lifecycle (via REST API):**
- Look up ticket status by number
- Create incident tickets — *admin only*
- Add work notes (auto-advances state New → In Progress) — *admin only*
- Resolve tickets with resolution notes and code — *admin only*
- Close tickets — *admin only*

**Role-Based Access Control (RBAC):**
- Authorization enforced by Entra ID security group membership (SG-IT-Operations)
- Admins (group members) get full read + write access
- Standard users get read-only access — write operations are blocked at the backend
- Permission check runs at login via Graph `/me/checkMemberGroups`; enforced on every tool call

## 🔐 Authorization Model (RBAC)

Authentication confirms *who you are*. Authorization confirms *what you're allowed to do*. This project implements both.

```
User signs in via Entra ID (MSAL)
  │
  ▼
App calls Graph /me/checkMemberGroups against SG-IT-Operations Object ID
  │
  ├─ Member?  → is_admin = True  → full read + write access
  └─ Not a member? → is_admin = False → read-only access
  │
  ▼
On every tool call, process_tool_calls checks:
  - Is this a WRITE operation? AND is the user NOT an admin?
    → Return "Access denied — requires administrator privileges"
  - Otherwise → execute the operation
```

**Access matrix:**

| Operation | Admin (SG-IT-Operations) | Standard User |
|-----------|:------------------------:|:-------------:|
| Look up users / groups / members | ✅ | ✅ |
| List all users / groups | ✅ | ✅ |
| Check ticket status | ✅ | ✅ |
| Reset password | ✅ | ❌ Blocked |
| Disable / enable account | ✅ | ❌ Blocked |
| Create / update / resolve / close tickets | ✅ | ❌ Blocked |

Enforcement happens server-side in `process_tool_calls` — the AI attempts the operation, and the backend RBAC layer either permits or denies it. The AI does not self-police permissions; the authorization decision is made by code, not the model.

## 🏗️ Architecture

![Architecture](diagrams/architecture.png)

## 🔍 Integration Details

### AD Integration — Dual Token Architecture

Read operations use the signed-in user's **delegated token**; write operations use an **application token** via client credentials with a User Administrator directory role assigned to the service principal.

### ServiceNow Integration — REST API + Basic Auth

A dedicated `chatbot.integration` user (roles `itil` + `rest_api_explorer`, Machine identity type) handles all ServiceNow API calls via Basic Auth. Full incident lifecycle support.

### Supported Operations

| Operation | Function | System | Access |
|-----------|----------|--------|:------:|
| User lookup | `get_user_info` | AD | All |
| Group membership | `get_user_groups` | AD | All |
| Group members | `get_group_members` | AD | All |
| All users | `list_all_users` | AD | All |
| All groups | `list_all_groups` | AD | All |
| Disabled accounts | `get_disabled_users` | AD | All |
| Ticket status | `get_ticket_status` | ServiceNow | All |
| Password reset | `reset_user_password` | AD | Admin |
| Disable account | `disable_user_account` | AD | Admin |
| Enable account | `enable_user_account` | AD | Admin |
| Create ticket | `create_servicenow_ticket` | ServiceNow | Admin |
| Add work note | `add_work_note` | ServiceNow | Admin |
| Resolve ticket | `resolve_ticket` | ServiceNow | Admin |
| Close ticket | `close_ticket` | ServiceNow | Admin |

## 🔐 Security Controls

| Layer | Implementation |
|-------|---------------|
| **Authentication** | Microsoft Entra ID with MSAL |
| **Authorization** | RBAC via Entra ID group membership (SG-IT-Operations) |
| **MFA** | Conditional Access policy |
| **Secrets Management** | Azure Key Vault (Graph + ServiceNow credentials) |
| **Service Auth** | Managed Identity for Azure-to-Azure |
| **HTTPS Enforcement** | App Service HTTPS Only + ProxyFix middleware |
| **Security Headers** | X-Content-Type-Options, HSTS, X-Frame-Options, XSS Protection |
| **Graph Token Separation** | Delegated for reads, Application for writes |
| **Least Privilege** | Write operations gated; ServiceNow uses scoped non-human account |
| **Hybrid AD Awareness** | Blocks cloud writes on on-prem synced accounts |
| **Audit Logging** | Every login (with admin status), query, and tool call logged |
| **Session Management** | Server-side Flask sessions |
| **CSRF Protection** | State parameter validation on OAuth callbacks |

## 🔗 Connected Environments

| System | Details |
|--------|---------|
| **On-Prem AD** | amoghlab.local on Oracle Cloud, Windows Server 2022, 15+ users, 8+ GPOs, LAPS, Tiered Admin Model — [Windows-AD-Lab](https://github.com/Amogh-Karankal/Windows-AD-Lab) |
| **Cloud AD** | Entra ID tenant synced via Entra Connect with Password Hash Sync |
| **ServiceNow** | Personal Developer Instance (Yokohama), incident management module |

## 📁 Project Structure

```
azure-secure-ai-chatbot/
├── app/
│   ├── app.py                  # Flask app — ProxyFix, dual-token routing, RBAC enforcement
│   ├── auth_config.py          # Local config (Entra + ServiceNow creds)
│   ├── auth_config_azure.py    # Azure config (Key Vault + Managed Identity)
│   ├── graph_helpers.py        # AD operations, RBAC check, tool definitions
│   ├── servicenow_helpers.py   # ServiceNow ticket lifecycle operations
│   ├── requirements.txt
│   ├── templates/              # login.html, chat.html
│   └── static/                 # style.css
├── diagrams/
│   └── architecture.png
├── screenshots/
├── README.md
└── LICENSE
```

## 🚀 Deployment

### Prerequisites

- Azure subscription with App Service, OpenAI, Key Vault
- Microsoft Entra ID tenant with app registration and an admin security group (e.g. SG-IT-Operations)
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

Set the admin group Object ID in `graph_helpers.py` (`ADMIN_GROUP_ID`) to match your environment's admin security group.

### Azure App Service Deployment

1. Create App Service (Python 3.11), enable system-assigned Managed Identity
2. Create Azure Key Vault, store secrets including `SERVICENOW-PASSWORD`
3. Grant Managed Identity Key Vault Secrets User and Cognitive Services OpenAI User roles
4. Configure env vars: `KEY_VAULT_NAME`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `SERVICENOW_INSTANCE`, `SERVICENOW_USER`
5. Startup command: `gunicorn --bind=0.0.0.0 --timeout 600 app:app`
6. Enable HTTPS Only
7. Add redirect URI to Entra app: `https://your-app.azurewebsites.net/getAToken`
8. Grant admin consent for Graph permissions (Delegated + Application)
9. Assign User Administrator role to the app's service principal
10. Deploy code via Kudu SSH or VS Code

### Troubleshooting

| Issue | Fix |
|-------|-----|
| Redirect URI mismatch | Verify both `localhost` and App Service URL added to app registration |
| `http://` instead of `https://` | ProxyFix middleware handles this — ensure updated `app.py` is deployed |
| Password reset returns 403 | Assign User Administrator role to app service principal |
| Admin user shows as non-admin | Confirm `ADMIN_GROUP_ID` matches your group's Object ID; clear `flask_session` and re-login |
| AI refuses write without trying | System prompt instructs the model to attempt operations and let the backend enforce RBAC |
| ServiceNow API 401 | Verify `chatbot.integration` has `itil` + `rest_api_explorer` roles |
| ServiceNow Resolution code rejected | Use valid Yokohama values: 'Solution provided', 'Workaround provided', etc. |
| ServiceNow PDI hibernated | Log into developer.servicenow.com to wake it (5-10 min) |

## 🛠️ Technologies

| Category | Technology |
|----------|-----------|
| **AI** | Azure OpenAI (GPT-4o), Function Calling (14 tools) |
| **Backend** | Python, Flask, Gunicorn |
| **Authentication** | Microsoft Entra ID, MSAL, Conditional Access |
| **Authorization** | RBAC via Graph group-membership check |
| **AD Integration** | Microsoft Graph API, Entra Connect |
| **Ticketing** | ServiceNow REST API (Yokohama) |
| **Token Architecture** | Delegated (reads) + Application (writes) for Graph; Basic Auth for ServiceNow |
| **Secrets** | Azure Key Vault, Managed Identity |
| **Hosting** | Azure App Service (B1) |
| **Proxy** | Werkzeug ProxyFix |

## 📈 Future Enhancements

- Auto-create ServiceNow ticket when password reset is performed (audit trail)
- Azure Content Safety integration for input filtering
- RAG with IT knowledge base articles
- Markdown rendering in chat
- Tiered RBAC (different permission levels for different admin groups)

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
