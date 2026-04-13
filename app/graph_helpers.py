"""
graph_helpers.py — Microsoft Graph API helpers for AD queries
Queries synced on-prem AD data via Microsoft Graph API
"""

import requests
import json


GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _graph_get(endpoint, token):
    """Make authenticated GET request to Microsoft Graph"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.get(f"{GRAPH_BASE}{endpoint}", headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"Graph API error {response.status_code}: {response.text}"}


def get_user_info(token, username):
    """Get user details by display name or UPN"""
    # Search by display name or userPrincipalName
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
            "createdDateTime": user.get("createdDateTime")
        })
    return {"users": results}


def get_user_groups(token, username):
    """Get group memberships for a user"""
    # First find the user
    user_data = _graph_get(
        f"/users?$filter=startswith(displayName,'{username}') or startswith(userPrincipalName,'{username}')&$select=id,displayName",
        token
    )
    if "error" in user_data:
        return user_data
    
    users = user_data.get("value", [])
    if not users:
        return {"result": f"No user found matching '{username}'"}
    
    user_id = users[0]["id"]
    display_name = users[0]["displayName"]
    
    # Get group memberships
    groups_data = _graph_get(f"/users/{user_id}/memberOf?$select=displayName,groupTypes,securityEnabled", token)
    if "error" in groups_data:
        return groups_data
    
    groups = []
    for group in groups_data.get("value", []):
        if group.get("@odata.type") == "#microsoft.graph.group":
            groups.append({
                "name": group.get("displayName"),
                "securityEnabled": group.get("securityEnabled")
            })
    
    return {"user": display_name, "groups": groups, "count": len(groups)}


def get_group_members(token, group_name):
    """Get members of a specific group"""
    # Find the group
    group_data = _graph_get(
        f"/groups?$filter=displayName eq '{group_name}'&$select=id,displayName",
        token
    )
    if "error" in group_data:
        return group_data
    
    groups = group_data.get("value", [])
    if not groups:
        return {"result": f"No group found matching '{group_name}'"}
    
    group_id = groups[0]["id"]
    group_display = groups[0]["displayName"]
    
    # Get members
    members_data = _graph_get(f"/groups/{group_id}/members?$select=displayName,userPrincipalName,accountEnabled", token)
    if "error" in members_data:
        return members_data
    
    members = []
    for member in members_data.get("value", []):
        members.append({
            "displayName": member.get("displayName"),
            "userPrincipalName": member.get("userPrincipalName"),
            "accountEnabled": member.get("accountEnabled")
        })
    
    return {"group": group_display, "members": members, "count": len(members)}


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
        "/groups?$filter=securityEnabled eq true&$select=displayName,description,securityEnabled&$top=50",
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


# Map function names to actual functions
FUNCTION_MAP = {
    "get_user_info": get_user_info,
    "get_user_groups": get_user_groups,
    "get_group_members": get_group_members,
    "list_all_users": list_all_users,
    "list_all_groups": list_all_groups,
    "get_disabled_users": get_disabled_users,
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
    }
]