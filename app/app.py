import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix
import msal
from openai import AzureOpenAI

RUNNING_IN_AZURE = os.getenv("WEBSITE_HOSTNAME") is not None

if RUNNING_IN_AZURE:
    import auth_config_azure as auth_config
else:
    from dotenv import load_dotenv
    load_dotenv()
    import auth_config

from graph_helpers import FUNCTION_MAP, AD_TOOLS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config["SECRET_KEY"] = auth_config.FLASK_SECRET_KEY
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

def get_openai_client():
    if RUNNING_IN_AZURE:
        try:
            from azure.identity import ManagedIdentityCredential
            credential = ManagedIdentityCredential()
            token = credential.get_token("https://cognitiveservices.azure.com/.default")
            return AzureOpenAI(azure_endpoint=auth_config.AZURE_OPENAI_ENDPOINT, api_version="2024-02-15-preview", azure_ad_token=token.token)
        except Exception as e:
            logger.error(f"Managed Identity failed: {e}")
            if hasattr(auth_config, 'AZURE_OPENAI_KEY') and auth_config.AZURE_OPENAI_KEY:
                return AzureOpenAI(api_key=auth_config.AZURE_OPENAI_KEY, api_version="2024-02-15-preview", azure_endpoint=auth_config.AZURE_OPENAI_ENDPOINT)
            raise e
    else:
        return AzureOpenAI(api_key=auth_config.AZURE_OPENAI_KEY, api_version="2024-02-15-preview", azure_endpoint=auth_config.AZURE_OPENAI_ENDPOINT)

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

SYSTEM_PROMPT = """You are an IT Helpdesk Assistant with access to Active Directory data and account management capabilities.

You can:
- Look up user accounts, check group memberships, and query directory information
- Reset user passwords (generates a temporary password, forces change on next login)
- Disable user accounts (for offboarding or security incidents)
- Re-enable disabled user accounts

When answering AD-related questions:
- Use the appropriate tool to get real data before answering.
- Always present information clearly and accurately.
- Do not make up information.
- Present the results in a clear, formatted way.
- If a tool returns an error, explain the issue clearly.

For password resets:
- Always confirm the user's identity before resetting.
- Display the temporary password clearly so the admin can share it with the user.
- Remind the admin that the user will be forced to change the password on next sign-in.

For account disable/enable:
- Confirm which account will be affected before proceeding.
- If the account is synced from on-premises AD, explain that the action must be performed on the domain controller.

You can also answer general IT questions without using tools.
Be concise and helpful."""

def _get_graph_token():
    try:
        token_result = _get_token_from_cache(auth_config.SCOPE)
        if token_result and "access_token" in token_result:
            return token_result["access_token"]
    except Exception as e:
        logger.error(f"Failed to get Graph token: {e}")
    return None

def process_tool_calls(response, messages, openai_client, graph_token):
    message = response.choices[0].message
    while message.tool_calls:
        messages.append(message)
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            logger.info(f"AD QUERY - Function: {func_name}, Args: {func_args}")
            if func_name in FUNCTION_MAP:
                func = FUNCTION_MAP[func_name]
                if "username" in func_args:
                    result = func(graph_token, func_args["username"])
                elif "group_name" in func_args:
                    result = func(graph_token, func_args["group_name"])
                else:
                    result = func(graph_token)
            else:
                result = {"error": f"Unknown function: {func_name}"}
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})
        response = openai_client.chat.completions.create(model=auth_config.AZURE_OPENAI_DEPLOYMENT, messages=messages, tools=AD_TOOLS, max_tokens=1000, temperature=0.3)
        message = response.choices[0].message
    return message.content

def get_chat_history():
    if "chat_history" not in session:
        session["chat_history"] = []
    return session["chat_history"]

def add_to_chat_history(role, content):
    history = get_chat_history()
    history.append({"role": role, "content": content})
    session["chat_history"] = history

def _build_msal_app(cache=None):
    return msal.ConfidentialClientApplication(auth_config.CLIENT_ID, authority=auth_config.AUTHORITY, client_credential=auth_config.CLIENT_SECRET, token_cache=cache)

def _build_auth_url(scopes=None, state=None):
    return _build_msal_app().get_authorization_request_url(scopes or [], state=state, redirect_uri=url_for("authorized", _external=True))

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
        logger.warning("State mismatch - possible CSRF attack")
        return redirect(url_for("index"))
    if "error" in request.args:
        logger.error(f"Auth error: {request.args.get('error_description')}")
        return render_template("login.html", error=request.args.get("error_description"))
    if request.args.get("code"):
        cache = msal.SerializableTokenCache()
        result = _build_msal_app(cache).acquire_token_by_authorization_code(request.args["code"], scopes=auth_config.SCOPE, redirect_uri=url_for("authorized", _external=True))
        if "error" in result:
            logger.error(f"Token error: {result.get('error_description')}")
            return render_template("login.html", error=result.get("error_description"))
        session["user"] = result.get("id_token_claims")
        session["token_cache"] = cache.serialize()
        username = session["user"].get("preferred_username", "unknown")
        logger.info(f"LOGIN SUCCESS - User: {username}")
    return redirect(url_for("index"))

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
                graph_token = _get_graph_token()
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                messages.extend(get_chat_history())
                response = openai_client.chat.completions.create(model=auth_config.AZURE_OPENAI_DEPLOYMENT, messages=messages, tools=AD_TOOLS if graph_token else None, max_tokens=1000, temperature=0.3)
                if response.choices[0].message.tool_calls and graph_token:
                    assistant_message = process_tool_calls(response, messages, openai_client, graph_token)
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
    return redirect(auth_config.AUTHORITY + "/oauth2/v2.0/logout" + "?post_logout_redirect_uri=" + url_for("index", _external=True))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
