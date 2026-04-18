"""
graph_helpers.py — Microsoft Graph API helpers for AD queries and actions
Queries synced on-prem AD data via Microsoft Graph API (delegated token for reads)
Uses application token for write operations (password reset, enable/disable)
"""

import os
import requests
import json
import string
import secrets
import msal


GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _get_app_token():
    """Get an application-level token for write operations (password reset, enable/disable)"""
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
    """Make authenticated GET request to Microsoft Graph"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.get(f"{GRAPH_BASE}{endpoint}", headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"Graph API error {response.status_code}: {response.text}"}


def _graph_patch(endpoint, token, body):
    """Make authenticated PATCH request to Microsoft Graph"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.patch(f"{GRAPH_BASE}{endpoint}", headers=headers, json=body)
    if response.status_code in (200, 204):
        return {"success": True}
    else:
        return {"error": f"Graph API error {response.status_code}: {response.text}"}


def _find_user_id(token, username):
    """Find a user's ID by display name or UPN prefix"""
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
    """Get user details by display name or UPN"""
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
    """Get group memberships for a user"""
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
    """Get members of a specific group"""
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
    """List all users in the directory"""
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
    """List all security groups"""
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
    """Get all disabled user accounts"""
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
    """Reset a user's password to a temporary password (uses application token)"""
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
        return {"error": "Could not obtain application token for password reset. Check app registration credentials."}

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
    """Disable a user account (uses application token for the write)"""
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
            "error": f"Cannot disable '{user_info.get('displayName')}' via cloud — this account is synced from on-premises AD. Disable it on the domain controller; the change will sync to Entra ID.",
            "user": user_info.get("displayName"),
            "onPremisesSynced": True
        }

    app_token = _get_app_token()
    if not app_token:
        return {"error": "Could not obtain application token for account disable. Check app registration credentials."}

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
    """Enable a disabled user account (uses application token for the write)"""
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
            "error": f"Cannot enable '{user_info.get('displayName')}' via cloud — this account is synced from on-premises AD. Enable it on the domain controller; the change will sync to Entra ID.",
            "user": user_info.get("displayName"),
            "onPremisesSynced": True
        }

    app_token = _get_app_token()
    if not app_token:
        return {"error": "Could not obtain application token for account enable. Check app registration credentials."}

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
    """Generate a secure temporary password meeting complexity requirements"""
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
}

# OpenAI function/tool definitions
AD_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_user_info",
            "description": "Get information about a user in Active Directory — account status, department, job title, whether synced from on-prem AD",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "The user's display name or username (e.g. 'John Smith' or 'john.smith')"
                    }
                },
                "required": ["username"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_groups",
            "description": "Get all group memberships for a specific user",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "The user's display name or username"
                    }
                },
                "required": ["username"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_group_members",
            "description": "Get all members of a specific security group",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_name": {
                        "type": "string",
                        "description": "The exact name of the security group (e.g. 'IT_Admins', 'Tier0-DomainAdmins')"
                    }
                },
                "required": ["group_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_all_users",
            "description": "List all users in the directory with their status and department",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_all_groups",
            "description": "List all security groups in the directory",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_disabled_users",
            "description": "Get all disabled/inactive user accounts",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reset_user_password",
            "description": "Reset a user's password to a temporary password. The user will be forced to change it on next sign-in. Only works for cloud-only accounts, not on-prem synced accounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "The user's display name or username to reset password for"
                    }
                },
                "required": ["username"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "disable_user_account",
            "description": "Disable a user account (e.g. for offboarding or security incidents). Only works for cloud-only accounts, not on-prem synced accounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "The user's display name or username to disable"
                    }
                },
                "required": ["username"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "enable_user_account",
            "description": "Re-enable a disabled user account. Only works for cloud-only accounts, not on-prem synced accounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "The user's display name or username to enable"
                    }
                },
                "required": ["username"]
            }
        }
    },
]
