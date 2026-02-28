import os
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

# Configure logging for audit trail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
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
            # Fallback to API key if available
            if auth_config.AZURE_OPENAI_KEY:
                return AzureOpenAI(
                    api_key=auth_config.AZURE_OPENAI_KEY,
                    api_version="2024-02-15-preview",
                    azure_endpoint=auth_config.AZURE_OPENAI_ENDPOINT
                )
            raise e
    else:
        # Local development - use API key
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
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if RUNNING_IN_AZURE:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


def get_chat_history():
    if "chat_history" not in session:
        session["chat_history"] = []
    return session["chat_history"]


def add_to_chat_history(role, content):
    history = get_chat_history()
    history.append({"role": role, "content": content})
    session["chat_history"] = history


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
        redirect_uri=url_for("authorized", _external=True, _scheme='https' if RUNNING_IN_AZURE else 'http')
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
        result = _build_msal_app(cache).acquire_token_by_authorization_code(
            request.args["code"],
            scopes=auth_config.SCOPE,
            redirect_uri=url_for("authorized", _external=True, _scheme='https' if RUNNING_IN_AZURE else 'http')
        )
        
        if "error" in result:
            logger.error(f"Token error: {result.get('error_description')}")
            return render_template("login.html", error=result.get("error_description"))
        
        session["user"] = result.get("id_token_claims")
        session["token_cache"] = cache.serialize()
        
        logger.info(f"LOGIN SUCCESS - User: {session['user'].get('preferred_username')}")
        
    return redirect(url_for("chat"))


@app.route("/logout")
def logout():
    username = session.get("user", {}).get("preferred_username", "unknown")
    logger.info(f"LOGOUT - User: {username}")
    
    session.clear()
    
    # Build post-logout redirect
    if RUNNING_IN_AZURE:
        post_logout = url_for('index', _external=True, _scheme='https')
    else:
        post_logout = url_for('index', _external=True)
    
    return redirect(
        f"{auth_config.AUTHORITY}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={post_logout}"
    )


@app.route("/chat", methods=["GET", "POST"])
def chat():
    if not session.get("user"):
        logger.warning("Unauthenticated access attempt to /chat")
        return redirect(url_for("login"))
    
    token = _get_token_from_cache(auth_config.SCOPE)
    if not token:
        logger.warning("Token expired, redirecting to login")
        return redirect(url_for("login"))
    
    user = session["user"]
    username = user.get("preferred_username", "User")
    
    if request.method == "POST":
        user_message = request.form.get("message", "").strip()
        
        if user_message:
            logger.info(f"CHAT INPUT - User: {username} - Message: {user_message[:100]}...")
            
            add_to_chat_history("user", user_message)
            
            try:
                messages = [
                    {
                        "role": "system",
                        "content": "You are a helpful AI assistant. Be concise and helpful."
                    }
                ]
                messages.extend(get_chat_history())
                
                openai_client = get_openai_client()
                response = openai_client.chat.completions.create(
                    model=auth_config.AZURE_OPENAI_DEPLOYMENT,
                    messages=messages,
                    max_tokens=1000,
                    temperature=0.7
                )
                
                assistant_message = response.choices[0].message.content
                
                add_to_chat_history("assistant", assistant_message)
                
                logger.info(f"CHAT OUTPUT - User: {username} - Response: {assistant_message[:100]}...")
                
            except Exception as e:
                logger.error(f"OpenAI Error - User: {username} - Error: {str(e)}")
                add_to_chat_history("assistant", f"Sorry, an error occurred: {str(e)}")
    
    return render_template(
        "chat.html",
        user=user,
        chat_history=get_chat_history()
    )


@app.route("/clear")
def clear_chat():
    if session.get("user"):
        username = session["user"].get("preferred_username", "unknown")
        logger.info(f"CHAT CLEARED - User: {username}")
        session["chat_history"] = []
    return redirect(url_for("chat"))


@app.route("/health")
def health():
    """Health check endpoint"""
    return {"status": "healthy"}, 200


if __name__ == "__main__":
    app.run(debug=True, host="localhost", port=5000)