import os
import logging
from flask import session, redirect, url_for, request, jsonify
from auth0.authentication import GetToken, Social
import requests
import secrets
import hashlib
import base64
from decouple import config

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self, app):
        self.app = app
        self.auth0_domain = os.getenv("AUTH0_DOMAIN")
        self.auth0_client_id = os.getenv("AUTH0_CLIENT_ID")
        self.auth0_client_secret = os.getenv("AUTH0_CLIENT_SECRET")
        self.auth0_callback_url = os.getenv("AUTH0_CALLBACK_URL")
        self.fitbit_client_id = os.getenv("FITBIT_CLIENT_ID")
        self.fitbit_client_secret = os.getenv("FITBIT_CLIENT_SECRET")
        self.fitbit_auth_url = "https://www.fitbit.com/oauth2/authorize"
        self.fitbit_token_url = "https://api.fitbit.com/oauth2/token"
        self.fitbit_api_url = "https://api.fitbit.com/1/user/-/"

        self.app.route('/auth0/login')(self.auth0_login)
        self.app.route('/auth0/callback')(self.auth0_callback)
        self.app.route('/auth0/logout')(self.auth0_logout)
        self.app.route('/fitbit/login')(self.fitbit_login)
        self.app.route('/callback')(self.callback)
        self.app.route('/logout')(self.logout)

    def generate_pkce_values(self):
        code_verifier = secrets.token_urlsafe(32)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).rstrip(b'=').decode('utf-8')
        state = secrets.token_urlsafe(16)
        return code_verifier, code_challenge, state

    def auth0_login(self):
        return redirect(
            f"https://{self.auth0_domain}/authorize?response_type=code&client_id={self.auth0_client_id}&redirect_uri={self.auth0_callback_url}&scope=openid%20profile%20email"
        )

    def auth0_callback(self):
        code = request.args.get('code')
        if not code:
            return jsonify({"error": "Authorization code not found"}), 400

        token_client = GetToken(self.auth0_domain, self.auth0_client_id, client_secret=self.auth0_client_secret)
        token_response = token_client.authorization_code(code, redirect_uri=self.auth0_callback_url)

        session['auth0_user'] = token_response['id_token']
        session['access_token'] = token_response['access_token']
        session.modified = True
        logger.debug(f"Auth0 Session: {dict(session)}")
        return redirect(url_for('chat_get'))  # Updated to 'chat_get'

    def auth0_logout(self):
        session.clear()
        return redirect(
            f"https://{self.auth0_domain}/v2/logout?client_id={self.auth0_client_id}&returnTo={url_for('index', _external=True)}"
        )

    def fitbit_login(self):
        code_verifier, code_challenge, state = self.generate_pkce_values()
        session['code_verifier'] = code_verifier
        session['state'] = state

        params = {
            "response_type": "code",
            "client_id": self.fitbit_client_id,
            "redirect_uri": "http://127.0.0.1:5000/callback",
            "scope": "activity heartrate oxygen_saturation temperature",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state
        }

        auth_url = f"{self.fitbit_auth_url}?" + "&".join(f"{k}={requests.utils.quote(v)}" for k, v in params.items())
        logger.debug(f"Fitbit Authorization URL: {auth_url}")
        return redirect(auth_url)

    def callback(self):
        code = request.args.get('code')
        state = request.args.get('state')

        if not code or state != session.get('state'):
            return "Authorization failed: Invalid state or code.", 400

        auth_header = base64.b64encode(f"{self.fitbit_client_id}:{self.fitbit_client_secret}".encode()).decode()
        token_response = requests.post(
            self.fitbit_token_url,
            headers={"Authorization": f"Basic {auth_header}"},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "http://127.0.0.1:5000/callback",
                "code_verifier": session.get('code_verifier', '')
            }
        )

        if token_response.status_code != 200:
            logger.error(f"Token exchange failed: {token_response.text}")
            return f"Token exchange failed: {token_response.text}", 400

        token_data = token_response.json()
        logger.debug(f"✅ Scopes: {token_data.get('scope')}")

        session['fitbit_user'] = True
        session['access_token'] = token_data['access_token']
        session['refresh_token'] = token_data.get('refresh_token')
        session.modified = True
        logger.debug(f"✅ Session after saving token: {session}")

        return redirect(url_for('chat_get'))  # Updated to 'chat_get'

    def logout(self):
        session.clear()
        return redirect(url_for('index'))