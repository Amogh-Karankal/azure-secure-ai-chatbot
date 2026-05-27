"""
graph_helpers.py — Microsoft Graph API helpers for AD queries and actions
Plus ServiceNow ticket management integration
"""

import os
import requests
import json
import string
import secrets
import msal

from servicenow_helpers import (
    create_servicenow_ticket,
    get_ticket_status,
    add_work_note,
    resolve_ticket,
    close_ticket,
)


GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _get_app_token():
    try:
        if os.getenv("WEBSITE_HOSTNAME"):
            import auth_config_azure as config
        else:
            import auth_config as config

        app = msal.ConfidentialClientApplication(
            config.CLIENT_ID,
            authority=config.AUTHORITY,
            client_credential=config.CLIENT_SECRET
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" in result:
            return result["access_token"]
        return None
    except Exception as e:
        return None


def _graph_get(endpoint, token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.get(f"{GRAPH_BASE}{endpoint}", headers=headers)
    if response.status_code == 200:
        return response.json()
    return {"error": f"Graph API error {response.status_code}: {response.text}"}


def _graph_patch(endpoint, token, body):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.patch(f"{GRAPH_BASE}{endpoint}", headers=headers, json=body)
    if response.status_code in (200, 204):
        return {"success": True}
    return {"error": f"Graph API error {response.status_code}: {response.text}"}


def _find_user_id(token, username):
    data = _graph_get(
        f"/users?$filter=startswith(displayName,'{username}') or startswith(userPrincipalName,'{username}')&$select=id,displayName,userPrincipalName",
        token
    )
    if "error" in data:
        return None, data
    users = data.get("value", [])
    if not users:
        return None, {"error": f"No user found matching '{username}'"}
    return users[0]["id"], users[0]


def get_user_info(token, username):
    data = _graph_get(
        f"/users?$filter=startswith(displayName,'{username}') or startswith(userPrincipalName,'{username}')&$select=displayName,userPrincipalName,jobTitle,department,accountEnabled,onPremisesSyncEnabled,createdDateTime,lastSignInDateTime",
        token
    )
    if "error" in data:
        return data
    users = data.get("value", [])
    if not users:
        return {"result": f"No user found matching '{username}'"}
    results = []
    for user in users:
        results.append({
            "displayName": user.get("displayName"),
            "userPrincipalName": user.get("userPrincipalName"),
            "jobTitle": user.get("jobTitle"),
            "department": user.get("department"),
            "accountEnabled": user.get("accountEnabled"),
            "onPremisesSynced": user.get("onPremisesSyncEnabled", False),
            "createdDateTime": user.get("createdDateTime"),
        })
    return {"users": results, "count": len(results)}


def get_user_groups(token, username):
    user_id, user_info = _find_user_id(token, username)
    if not user_id:
        return user_info
    data = _graph_get(f"/users/{user_id}/memberOf?$select=displayName,groupTypes,securityEnabled,mailEnabled", token)
    if "error" in data:
        return data
    groups = []
    for group in data.get("value", []):
        if group.get("@odata.type") == "#microsoft.graph.group":
            groups.append({
                "name": group.get("displayName"),
                "securityEnabled": group.get("securityEnabled"),
                "type": "Security" if group.get("securityEnabled") else "Microsoft 365"
            })
    return {"user": user_info.get("displayName"), "groups": groups, "count": len(groups)}


def get_group_members(token, group_name):
    data = _graph_get(
        f"/groups?$filter=displayName eq '{group_name}'&$select=id,displayName",
        token
    )
    if "error" in data:
        return data
    groups = data.get("value", [])
    if not groups:
        return {"result": f"No group found with name '{group_name}'"}
    group_id = groups[0]["id"]
    members_data = _graph_get(
        f"/groups/{group_id}/members?$select=displayName,userPrincipalName,accountEnabled",
        token
    )
    if "error" in members_data:
        return members_data
    members = []
    for member in members_data.get("value", []):
        members.append({
            "displayName": member.get("displayName"),
            "userPrincipalName": member.get("userPrincipalName"),
            "accountEnabled": member.get("accountEnabled")
        })
    return {"group": group_name, "members": members, "count": len(members)}


def list_all_users(token):
    data = _graph_get(
        "/users?$select=displayName,userPrincipalName,department,accountEnabled,onPremisesSyncEnabled&$top=50",
        token
    )
    if "error" in data:
        return data
    users = []
    for user in data.get("value", []):
        users.append({
            "displayName": user.get("displayName"),
            "userPrincipalName": user.get("userPrincipalName"),
            "department": user.get("department"),
            "accountEnabled": user.get("accountEnabled"),
            "onPremisesSynced": user.get("onPremisesSyncEnabled", False)
        })
    return {"users": users, "count": len(users)}


def list_all_groups(token):
    data = _graph_get(
        "/groups?$filter=securityEnabled eq true&$select=displayName,description,securityEnabled",
        token
    )
    if "error" in data:
        return data
    groups = []
    for group in data.get("value", []):
        groups.append({
            "name": group.get("displayName"),
            "description": group.get("description")
        })
    return {"groups": groups, "count": len(groups)}


def get_disabled_users(token):
    data = _graph_get(
        "/users?$filter=accountEnabled eq false&$select=displayName,userPrincipalName,department,onPremisesSyncEnabled",
        token
    )
    if "error" in data:
        return data
    users = []
    for user in data.get("value", []):
        users.append({
            "displayName": user.get("displayName"),
            "userPrincipalName": user.get("userPrincipalName"),
            "department": user.get("department"),
            "onPremisesSynced": user.get("onPremisesSyncEnabled", False)
        })
    return {"disabledUsers": users, "count": len(users)}


def reset_user_password(token, username):
    user_id, user_info = _find_user_id(token, username)
    if not user_id:
        return user_info
    user_details = _graph_get(f"/users/{user_id}?$select=displayName,userPrincipalName,onPremisesSyncEnabled", token)
    if "error" in user_details:
        return user_details
    if user_details.get("onPremisesSyncEnabled"):
        return {
            "error": f"Cannot reset password for '{user_info.get('displayName')}' — this account is synced from on-premises AD. Password must be reset on the domain controller or via SSPR if configured.",
            "user": user_info.get("displayName"),
            "onPremisesSynced": True
        }
    app_token = _get_app_token()
    if not app_token:
        return {"error": "Could not obtain application token for password reset."}
    temp_password = _generate_temp_password()
    body = {
        "passwordProfile": {
            "password": temp_password,
            "forceChangePasswordNextSignIn": True
        }
    }
    result = _graph_patch(f"/users/{user_id}", app_token, body)
    if "error" in result:
        return result
    return {
        "success": True,
        "user": user_info.get("displayName"),
        "userPrincipalName": user_info.get("userPrincipalName"),
        "temporaryPassword": temp_password,
        "forceChangeOnNextLogin": True,
        "message": f"Password reset for {user_info.get('displayName')}. User must change password on next sign-in."
    }


def disable_user_account(token, username):
    user_id, user_info = _find_user_id(token, username)
    if not user_id:
        return user_info
    user_details = _graph_get(f"/users/{user_id}?$select=displayName,userPrincipalName,accountEnabled,onPremisesSyncEnabled", token)
    if "error" in user_details:
        return user_details
    if not user_details.get("accountEnabled"):
        return {
            "message": f"Account for '{user_info.get('displayName')}' is already disabled.",
            "user": user_info.get("displayName"),
            "accountEnabled": False
        }
    if user_details.get("onPremisesSyncEnabled"):
        return {
            "error": f"Cannot disable '{user_info.get('displayName')}' via cloud — this account is synced from on-premises AD.",
            "user": user_info.get("displayName"),
            "onPremisesSynced": True
        }
    app_token = _get_app_token()
    if not app_token:
        return {"error": "Could not obtain application token for account disable."}
    body = {"accountEnabled": False}
    result = _graph_patch(f"/users/{user_id}", app_token, body)
    if "error" in result:
        return result
    return {
        "success": True,
        "user": user_info.get("displayName"),
        "userPrincipalName": user_info.get("userPrincipalName"),
        "accountEnabled": False,
        "message": f"Account for {user_info.get('displayName')} has been disabled."
    }


def enable_user_account(token, username):
    user_id, user_info = _find_user_id(token, username)
    if not user_id:
        return user_info
    user_details = _graph_get(f"/users/{user_id}?$select=displayName,userPrincipalName,accountEnabled,onPremisesSyncEnabled", token)
    if "error" in user_details:
        return user_details
    if user_details.get("accountEnabled"):
        return {
            "message": f"Account for '{user_info.get('displayName')}' is already enabled.",
            "user": user_info.get("displayName"),
            "accountEnabled": True
        }
    if user_details.get("onPremisesSyncEnabled"):
        return {
            "error": f"Cannot enable '{user_info.get('displayName')}' via cloud — this account is synced from on-premises AD.",
            "user": user_info.get("displayName"),
            "onPremisesSynced": True
        }
    app_token = _get_app_token()
    if not app_token:
        return {"error": "Could not obtain application token for account enable."}
    body = {"accountEnabled": True}
    result = _graph_patch(f"/users/{user_id}", app_token, body)
    if "error" in result:
        return result
    return {
        "success": True,
        "user": user_info.get("displayName"),
        "userPrincipalName": user_info.get("userPrincipalName"),
        "accountEnabled": True,
        "message": f"Account for {user_info.get('displayName')} has been re-enabled."
    }


def _generate_temp_password(length=16):
    upper = string.ascii_uppercase
    lower = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%&*"
    password = [
        secrets.choice(upper),
        secrets.choice(lower),
        secrets.choice(digits),
        secrets.choice(special),
    ]
    all_chars = upper + lower + digits + special
    password += [secrets.choice(all_chars) for _ in range(length - 4)]
    password_list = list(password)
    secrets.SystemRandom().shuffle(password_list)
    return "".join(password_list)


# Map function names to actual functions
FUNCTION_MAP = {
    "get_user_info": get_user_info,
    "get_user_groups": get_user_groups,
    "get_group_members": get_group_members,
    "list_all_users": list_all_users,
    "list_all_groups": list_all_groups,
    "get_disabled_users": get_disabled_users,
    "reset_user_password": reset_user_password,
    "disable_user_account": disable_user_account,
    "enable_user_account": enable_user_account,
    "create_servicenow_ticket": create_servicenow_ticket,
    "get_ticket_status": get_ticket_status,
    "add_work_note": add_work_note,
    "resolve_ticket": resolve_ticket,
    "close_ticket": close_ticket,
}

# Functions that don't need a Graph token (use their own auth)
NO_TOKEN_FUNCTIONS = {
    "create_servicenow_ticket",
    "get_ticket_status",
    "add_work_note",
    "resolve_ticket",
    "close_ticket",
}

# OpenAI function/tool definitions
AD_TOOLS = [
    {"type": "function", "function": {
        "name": "get_user_info",
        "description": "Get information about a user in Active Directory — account status, department, job title, whether synced from on-prem AD",
        "parameters": {"type": "object", "properties": {"username": {"type": "string", "description": "The user's display name or username"}}, "required": ["username"]}
    }},
    {"type": "function", "function": {
        "name": "get_user_groups",
        "description": "Get all group memberships for a specific user",
        "parameters": {"type": "object", "properties": {"username": {"type": "string", "description": "The user's display name or username"}}, "required": ["username"]}
    }},
    {"type": "function", "function": {
        "name": "get_group_members",
        "description": "Get all members of a specific security group",
        "parameters": {"type": "object", "properties": {"group_name": {"type": "string", "description": "The exact name of the security group"}}, "required": ["group_name"]}
    }},
    {"type": "function", "function": {
        "name": "list_all_users",
        "description": "List all users in the directory",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "list_all_groups",
        "description": "List all security groups in the directory",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "get_disabled_users",
        "description": "Get all disabled/inactive user accounts",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "reset_user_password",
        "description": "Reset a user's password to a temporary password. Only works for cloud-only accounts.",
        "parameters": {"type": "object", "properties": {"username": {"type": "string", "description": "The user's display name or username"}}, "required": ["username"]}
    }},
    {"type": "function", "function": {
        "name": "disable_user_account",
        "description": "Disable a user account. Only works for cloud-only accounts.",
        "parameters": {"type": "object", "properties": {"username": {"type": "string", "description": "The user's display name or username"}}, "required": ["username"]}
    }},
    {"type": "function", "function": {
        "name": "enable_user_account",
        "description": "Re-enable a disabled user account. Only works for cloud-only accounts.",
        "parameters": {"type": "object", "properties": {"username": {"type": "string", "description": "The user's display name or username"}}, "required": ["username"]}
    }},
    {"type": "function", "function": {
        "name": "create_servicenow_ticket",
        "description": "Create a new ServiceNow incident ticket for an IT issue. Use this when the user reports a problem or asks to log a ticket.",
        "parameters": {
            "type": "object",
            "properties": {
                "caller": {"type": "string", "description": "ServiceNow username of the person reporting the issue (e.g. 'bruce.wayne', 'clark.kent')"},
                "short_description": {"type": "string", "description": "Brief summary of the issue"},
                "description": {"type": "string", "description": "Detailed description of the issue"},
                "urgency": {"type": "integer", "description": "1=High, 2=Medium, 3=Low. Default 3.", "enum": [1, 2, 3]},
                "impact": {"type": "integer", "description": "1=High, 2=Medium, 3=Low. Default 3.", "enum": [1, 2, 3]},
                "category": {"type": "string", "description": "'inquiry', 'software', 'hardware', 'network'"},
                "assignment_group": {"type": "string", "description": "Group like 'Service Desk', 'Network', 'Hardware', 'Software'"}
            },
            "required": ["caller", "short_description"]
        }
    }},
    {"type": "function", "function": {
        "name": "get_ticket_status",
        "description": "Look up the current status of an existing ServiceNow ticket by ticket number",
        "parameters": {"type": "object", "properties": {"ticket_number": {"type": "string", "description": "Ticket number like 'INC0010001'"}}, "required": ["ticket_number"]}
    }},
    {"type": "function", "function": {
        "name": "add_work_note",
        "description": "Add a work note to an existing ticket. Automatically moves state from New to In Progress. Use when documenting troubleshooting steps or progress.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_number": {"type": "string", "description": "Ticket number like 'INC0010001'"},
                "note": {"type": "string", "description": "The work note content — what was done, what was tried, what was found"}
            },
            "required": ["ticket_number", "note"]
        }
    }},
    {"type": "function", "function": {
        "name": "resolve_ticket",
        "description": "Resolve a ticket. Use when the issue has been fixed and the user can confirm. Requires resolution notes describing the fix.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_number": {"type": "string", "description": "Ticket number like 'INC0010001'"},
                "resolution_notes": {"type": "string", "description": "Description of how the issue was resolved"},
                "resolution_code": {"type": "string", "description": "One of: 'Solution provided', 'Workaround provided', 'Resolved by caller', 'Resolved by change', 'Resolved by problem', 'Resolved by request', 'Known error', 'Duplicate', 'User error', 'No resolution provided'"}
            },
            "required": ["ticket_number", "resolution_notes"]
        }
    }},
    {"type": "function", "function": {
        "name": "close_ticket",
        "description": "Close a resolved ticket. Use when the user has confirmed resolution and the ticket can be finalized.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_number": {"type": "string", "description": "Ticket number like 'INC0010001'"},
                "close_notes": {"type": "string", "description": "Optional final close notes"}
            },
            "required": ["ticket_number"]
        }
    }},
]