import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from flask_session import Session
import msal
from openai import AzureOpenAI

# Check if running in Azure
RUNNING_IN_AZURE = os.getenv("WEBSITE_HOSTNAME") is not None

# Import the right config
if RUNNING_IN_AZURE:
    import auth_config_azure as auth_config
else:
    from dotenv import load_dotenv
    load_dotenv()
    import auth_config

# Import Graph API helpers
from graph_helpers import FUNCTION_MAP, AD_TOOLS

# Configure logging for audit trail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = auth_config.FLASK_SECRET_KEY
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


# Initialize Azure OpenAI client
def get_openai_client():
    """Get OpenAI client - uses Managed Identity in Azure, API key locally"""
    if RUNNING_IN_AZURE:
        try:
            from azure.identity import ManagedIdentityCredential
            credential = ManagedIdentityCredential()
            token = credential.get_token("https://cognitiveservices.azure.com/.default")
            return AzureOpenAI(
                azure_endpoint=auth_config.AZURE_OPENAI_ENDPOINT,
                api_version="2024-02-15-preview",
                azure_ad_token=token.token
            )
        except Exception as e:
            logger.error(f"Managed Identity failed: {e}")
            if auth_config.AZURE_OPENAI_KEY:
                return AzureOpenAI(
                    api_key=auth_config.AZURE_OPENAI_KEY,
                    api_version="2024-02-15-preview",
                    azure_endpoint=auth_config.AZURE_OPENAI_ENDPOINT
                )
            raise e
    else:
        return AzureOpenAI(
            api_key=auth_config.AZURE_OPENAI_KEY,
            api_version="2024-02-15-preview",
            azure_endpoint=auth_config.AZURE_OPENAI_ENDPOINT
        )


# Security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
    return response


# Chat history helpers
def get_chat_history():
    if "chat_history" not in session:
        session["chat_history"] = []
    return session["chat_history"]


def add_to_chat_history(role, content):
    history = get_chat_history()
    history.append({"role": role, "content": content})
    session["chat_history"] = history


# MSAL helper functions
def _build_msal_app(cache=None):
    return msal.ConfidentialClientApplication(
        auth_config.CLIENT_ID,
        authority=auth_config.AUTHORITY,
        client_credential=auth_config.CLIENT_SECRET,
        token_cache=cache
    )


def _build_auth_url(scopes=None, state=None):
    return _build_msal_app().get_authorization_request_url(
        scopes or [],
        state=state,
        redirect_uri=url_for("authorized", _external=True)
    )


def _get_token_from_cache(scope=None):
    cache = msal.SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    
    cca = _build_msal_app(cache)
    accounts = cca.get_accounts()
    
    if accounts:
        result = cca.acquire_token_silent(scope, account=accounts[0])
        session["token_cache"] = cache.serialize()
        return result
    return None


def _get_graph_token():
    """Get a valid Graph API access token from the cache"""
    token_result = _get_token_from_cache(auth_config.SCOPE)
    if token_result and "access_token" in token_result:
        return token_result["access_token"]
    return None


# System prompt for IT Helpdesk AI Assistant
SYSTEM_PROMPT = """You are an IT Helpdesk AI Assistant for the amoghlab.local Active Directory environment. 
You help helpdesk staff look up user information, check group memberships, and troubleshoot account issues.

You have access to the following tools to query the Microsoft Entra ID directory (synced from on-premises Active Directory):
- get_user_info: Look up a user's account status, department, job title
- get_user_groups: Check what groups a user belongs to
- get_group_members: See who is in a specific security group
- list_all_users: List all users in the directory
- list_all_groups: List all security groups
- get_disabled_users: Find all disabled accounts

When a user asks about AD information, USE the tools to get real data. Do not make up information.
Present the results in a clear, formatted way.
If a tool returns an error, explain the issue clearly.
You can also answer general IT questions without using tools.
Be concise and helpful."""


def process_tool_calls(response, messages, openai_client, graph_token):
    """Process function calls from OpenAI and return final response"""
    message = response.choices[0].message
    
    while message.tool_calls:
        # Add assistant message with tool calls to messages
        messages.append(message)
        
        # Process each tool call
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            
            logger.info(f"AD QUERY - Function: {func_name}, Args: {func_args}")
            
            # Call the appropriate function
            if func_name in FUNCTION_MAP:
                func = FUNCTION_MAP[func_name]
                # Functions that need username/group_name need the token
                if "username" in func_args:
                    result = func(graph_token, func_args["username"])
                elif "group_name" in func_args:
                    result = func(graph_token, func_args["group_name"])
                else:
                    result = func(graph_token)
            else:
                result = {"error": f"Unknown function: {func_name}"}
            
            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result)
            })
        
        # Get next response (AI processes the tool results)
        response = openai_client.chat.completions.create(
            model=auth_config.AZURE_OPENAI_DEPLOYMENT,
            messages=messages,
            tools=AD_TOOLS,
            max_tokens=1000,
            temperature=0.3
        )
        message = response.choices[0].message
    
    return message.content


# Routes
@app.route("/")
def index():
    if not session.get("user"):
        return render_template("login.html")
    return redirect(url_for("chat"))


@app.route("/login")
def login():
    session["state"] = os.urandom(16).hex()
    auth_url = _build_auth_url(scopes=auth_config.SCOPE, state=session["state"])
    return redirect(auth_url)


@app.route("/getAToken")
def authorized():
    if request.args.get("state") != session.get("state"):
        return redirect(url_for("index"))
    
    if "error" in request.args:
        return render_template("login.html", error=request.args.get("error_description"))
    
    if request.args.get("code"):
        cache = msal.SerializableTokenCache()
        if session.get("token_cache"):
            cache.deserialize(session["token_cache"])
        
        cca = _build_msal_app(cache)
        result = cca.acquire_token_by_authorization_code(
            request.args["code"],
            scopes=auth_config.SCOPE,
            redirect_uri=url_for("authorized", _external=True)
        )
        
        if "error" in result:
            return render_template("login.html", error=result.get("error_description"))
        
        session["user"] = result.get("id_token_claims")
        session["token_cache"] = cache.serialize()
        
        username = session["user"].get("preferred_username", "unknown")
        logger.info(f"LOGIN SUCCESS - User: {username}")
    
    return redirect(url_for("chat"))


@app.route("/chat", methods=["GET", "POST"])
def chat():
    if not session.get("user"):
        return redirect(url_for("index"))
    
    user = session["user"]
    username = user.get("preferred_username", "unknown")
    
    if request.method == "POST":
        user_message = request.form.get("message", "").strip()
        
        if user_message:
            add_to_chat_history("user", user_message)
            logger.info(f"CHAT INPUT - User: {username} - Message: {user_message[:100]}...")
            
            try:
                openai_client = get_openai_client()
                
                # Get Graph API token for AD queries
                graph_token = _get_graph_token()
                
                # Build messages with system prompt
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                messages.extend(get_chat_history())
                
                # Call OpenAI with tools
                response = openai_client.chat.completions.create(
                    model=auth_config.AZURE_OPENAI_DEPLOYMENT,
                    messages=messages,
                    tools=AD_TOOLS if graph_token else None,
                    max_tokens=1000,
                    temperature=0.3
                )
                
                # Check if the model wants to call functions
                if response.choices[0].message.tool_calls and graph_token:
                    assistant_message = process_tool_calls(
                        response, messages, openai_client, graph_token
                    )
                else:
                    assistant_message = response.choices[0].message.content
                
                if not assistant_message:
                    assistant_message = "I couldn't generate a response. Please try again."
                
                add_to_chat_history("assistant", assistant_message)
                logger.info(f"CHAT OUTPUT - User: {username} - Response: {assistant_message[:100]}...")
                
            except Exception as e:
                logger.error(f"OpenAI Error - User: {username} - Error: {str(e)}")
                error_msg = f"Sorry, an error occurred: {str(e)}"
                add_to_chat_history("assistant", error_msg)
    
    return render_template("chat.html", user=user, chat_history=get_chat_history())


@app.route("/clear")
def clear_chat():
    if session.get("user"):
        username = session["user"].get("preferred_username", "unknown")
        logger.info(f"CHAT CLEARED - User: {username}")
        session["chat_history"] = []
    return redirect(url_for("chat"))


@app.route("/logout")
def logout():
    if session.get("user"):
        username = session["user"].get("preferred_username", "unknown")
        logger.info(f"LOGOUT - User: {username}")
    session.clear()
    return redirect(
        auth_config.AUTHORITY + "/oauth2/v2.0/logout"
        + "?post_logout_redirect_uri=" + url_for("index", _external=True)
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)