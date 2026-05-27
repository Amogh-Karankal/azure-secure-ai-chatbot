"""
servicenow_helpers.py — ServiceNow REST API helpers for ticket management
Supports: create, lookup, add work notes, resolve, close
Uses Basic Auth with the chatbot.integration user
"""

import os
import requests
from requests.auth import HTTPBasicAuth


# ServiceNow state numeric values
STATE_NEW = "1"
STATE_IN_PROGRESS = "2"
STATE_ON_HOLD = "3"
STATE_RESOLVED = "6"
STATE_CLOSED = "7"
STATE_CANCELED = "8"

STATE_MAP = {
    "1": "New",
    "2": "In Progress",
    "3": "On Hold",
    "6": "Resolved",
    "7": "Closed",
    "8": "Canceled"
}


def _get_servicenow_config():
    """Load ServiceNow credentials from the right config based on environment"""
    if os.getenv("WEBSITE_HOSTNAME"):
        import auth_config_azure as config
    else:
        import auth_config as config
    return config


def _sn_get(endpoint):
    config = _get_servicenow_config()
    url = f"https://{config.SERVICENOW_INSTANCE}.service-now.com/api/now{endpoint}"
    response = requests.get(
        url,
        auth=HTTPBasicAuth(config.SERVICENOW_USER, config.SERVICENOW_PASSWORD),
        headers={"Accept": "application/json"}
    )
    if response.status_code == 200:
        return response.json()
    return {"error": f"ServiceNow API error {response.status_code}: {response.text}"}


def _sn_post(endpoint, body):
    config = _get_servicenow_config()
    url = f"https://{config.SERVICENOW_INSTANCE}.service-now.com/api/now{endpoint}"
    response = requests.post(
        url,
        auth=HTTPBasicAuth(config.SERVICENOW_USER, config.SERVICENOW_PASSWORD),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json=body
    )
    if response.status_code in (200, 201):
        return response.json()
    return {"error": f"ServiceNow API error {response.status_code}: {response.text}"}


def _sn_patch(endpoint, body):
    """PATCH request to update an existing record"""
    config = _get_servicenow_config()
    url = f"https://{config.SERVICENOW_INSTANCE}.service-now.com/api/now{endpoint}"
    response = requests.patch(
        url,
        auth=HTTPBasicAuth(config.SERVICENOW_USER, config.SERVICENOW_PASSWORD),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json=body
    )
    if response.status_code in (200, 204):
        if response.text:
            return response.json()
        return {"success": True}
    return {"error": f"ServiceNow API error {response.status_code}: {response.text}"}


def _find_user_sys_id(user_name):
    result = _sn_get(f"/table/sys_user?sysparm_query=user_name={user_name}&sysparm_fields=sys_id,name,user_name&sysparm_limit=1")
    if "error" in result:
        return None, result
    users = result.get("result", [])
    if not users:
        return None, {"error": f"ServiceNow user '{user_name}' not found"}
    return users[0]["sys_id"], users[0]


def _find_group_sys_id(group_name):
    result = _sn_get(f"/table/sys_user_group?sysparm_query=name={group_name}&sysparm_fields=sys_id,name&sysparm_limit=1")
    if "error" in result:
        return None
    groups = result.get("result", [])
    if not groups:
        return None
    return groups[0]["sys_id"]


def _find_ticket_sys_id(ticket_number):
    """Look up a ticket's sys_id by ticket number (e.g. INC0010001)"""
    result = _sn_get(f"/table/incident?sysparm_query=number={ticket_number}&sysparm_fields=sys_id,number,state&sysparm_limit=1")
    if "error" in result:
        return None, result
    tickets = result.get("result", [])
    if not tickets:
        return None, {"error": f"Ticket '{ticket_number}' not found"}
    return tickets[0]["sys_id"], tickets[0]


def create_servicenow_ticket(caller, short_description, description=None, urgency=3, impact=3, category=None, assignment_group=None):
    """Create an incident ticket in ServiceNow"""
    caller_sys_id, caller_info = _find_user_sys_id(caller)
    if not caller_sys_id:
        return caller_info

    body = {
        "caller_id": caller_sys_id,
        "short_description": short_description,
        "urgency": str(urgency),
        "impact": str(impact),
    }
    if description:
        body["description"] = description
    if category:
        body["category"] = category.lower()
    if assignment_group:
        group_sys_id = _find_group_sys_id(assignment_group)
        if group_sys_id:
            body["assignment_group"] = group_sys_id

    result = _sn_post("/table/incident", body)
    if "error" in result:
        return result

    ticket = result.get("result", {})
    return {
        "success": True,
        "ticket_number": ticket.get("number"),
        "sys_id": ticket.get("sys_id"),
        "caller": caller_info.get("name"),
        "short_description": short_description,
        "urgency": urgency,
        "impact": impact,
        "state": "New",
        "assignment_group": assignment_group or "Unassigned",
        "message": f"Ticket {ticket.get('number')} created successfully for {caller_info.get('name')}."
    }


def get_ticket_status(ticket_number):
    """Look up an existing ticket by ticket number"""
    result = _sn_get(f"/table/incident?sysparm_query=number={ticket_number}&sysparm_display_value=true&sysparm_fields=number,short_description,state,priority,caller_id,assignment_group,sys_created_on,work_notes,resolution_notes&sysparm_limit=1")
    if "error" in result:
        return result
    tickets = result.get("result", [])
    if not tickets:
        return {"error": f"Ticket '{ticket_number}' not found"}

    ticket = tickets[0]
    return {
        "ticket_number": ticket.get("number"),
        "short_description": ticket.get("short_description"),
        "state": ticket.get("state"),
        "priority": ticket.get("priority"),
        "caller": ticket.get("caller_id") or "Unknown",
        "assignment_group": ticket.get("assignment_group") or "Unassigned",
        "created": ticket.get("sys_created_on"),
        "resolution_notes": ticket.get("resolution_notes") or None
    }


def add_work_note(ticket_number, note):
    """Add a work note to an existing ticket. Optionally moves state from New to In Progress."""
    ticket_sys_id, ticket_info = _find_ticket_sys_id(ticket_number)
    if not ticket_sys_id:
        return ticket_info

    body = {"work_notes": note}
    # Auto-advance from New to In Progress when work begins
    if ticket_info.get("state") == STATE_NEW:
        body["state"] = STATE_IN_PROGRESS

    result = _sn_patch(f"/table/incident/{ticket_sys_id}", body)
    if "error" in result:
        return result

    return {
        "success": True,
        "ticket_number": ticket_number,
        "work_note_added": note,
        "state": "In Progress" if ticket_info.get("state") == STATE_NEW else STATE_MAP.get(ticket_info.get("state"), "Unknown"),
        "message": f"Work note added to {ticket_number}. State is now In Progress."
    }


def resolve_ticket(ticket_number, resolution_notes, resolution_code="Solution provided"):
    """Resolve a ticket with resolution notes and a resolution code"""
    ticket_sys_id, ticket_info = _find_ticket_sys_id(ticket_number)
    if not ticket_sys_id:
        return ticket_info

    body = {
        "state": STATE_RESOLVED,
        "close_code": resolution_code,
        "close_notes": resolution_notes,
        "resolution_notes": resolution_notes
    }

    result = _sn_patch(f"/table/incident/{ticket_sys_id}", body)
    if "error" in result:
        return result

    return {
        "success": True,
        "ticket_number": ticket_number,
        "state": "Resolved",
        "resolution_code": resolution_code,
        "resolution_notes": resolution_notes,
        "message": f"Ticket {ticket_number} has been resolved."
    }


def close_ticket(ticket_number, close_notes=None):
    """Close a resolved ticket"""
    ticket_sys_id, ticket_info = _find_ticket_sys_id(ticket_number)
    if not ticket_sys_id:
        return ticket_info

    body = {"state": STATE_CLOSED}
    if close_notes:
        body["work_notes"] = close_notes

    result = _sn_patch(f"/table/incident/{ticket_sys_id}", body)
    if "error" in result:
        return result

    return {
        "success": True,
        "ticket_number": ticket_number,
        "state": "Closed",
        "message": f"Ticket {ticket_number} has been closed."
    }