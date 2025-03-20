import logging
import requests
from datetime import datetime, timedelta
from decouple import config
import base64

logger = logging.getLogger(__name__)

class FitbitClient:
    def __init__(self):
        self.access_token = None
        self.refresh_token = None
        self.client_id = config("FITBIT_CLIENT_ID")
        self.client_secret = config("FITBIT_CLIENT_SECRET")
        self.token_url = "https://api.fitbit.com/oauth2/token"
        # Use environment-specific redirect URI
        self.environment = config("ENVIRONMENT", default="development")
        self.redirect_uri = config("FITBIT_REDIRECT_URI", default="http://127.0.0.1:5000/callback")

        # Override for production environment
        if self.environment.lower() == "production":
            self.redirect_uri = "https://healthsync-ai-chatbot.onrender.com/callback"

        logger.debug(f"FitbitClient Environment: {self.environment}")
        logger.debug(f"Fitbit Redirect URI: {self.redirect_uri}")

    def set_access_token(self, token):
        self.access_token = token

    def set_refresh_token(self, token):
        self.refresh_token = token

    def refresh_access_token(self):
        if not self.refresh_token:
            logger.error("No refresh token available to refresh access token")
            return False

        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        response = requests.post(
            self.token_url,
            headers={"Authorization": f"Basic {auth_header}"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id
            }
        )

        if response.status_code != 200:
            logger.error(f"Failed to refresh token: {response.text}")
            return False

        token_data = response.json()
        self.access_token = token_data['access_token']
        self.refresh_token = token_data.get('refresh_token', self.refresh_token)
        logger.debug(f"Refreshed access token: {self.access_token}")
        return True

    def get_fitbit_data(self):
        if not self.access_token:
            logger.error("No access token set for Fitbit API")
            return {"sp02": "N/A", "heart_rate": "N/A"}

        headers = {"Authorization": f"Bearer {self.access_token}"}
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        # Fetch SpO2 data
        sp02_response = requests.get(
            f"https://api.fitbit.com/1/user/-/spo2/date/{today}.json",
            headers=headers
        )
        sp02_value = "N/A"
        if sp02_response.status_code == 200 and sp02_response.json():
            sp02_value = sp02_response.json().get('value', {}).get('avg', "N/A")
        else:
            if sp02_response.status_code == 401:
                logger.error(f"SpO2 API error for {today}: {sp02_response.status_code} {sp02_response.reason} for url: {sp02_response.url}")
                if self.refresh_access_token():
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    sp02_response = requests.get(
                        f"https://api.fitbit.com/1/user/-/spo2/date/{today}.json",
                        headers=headers
                    )
                    if sp02_response.status_code == 200 and sp02_response.json():
                        sp02_value = sp02_response.json().get('value', {}).get('avg', "N/A")
            if sp02_response.status_code != 200:
                # Try yesterday's data as a fallback
                sp02_response_yesterday = requests.get(
                    f"https://api.fitbit.com/1/user/-/spo2/date/{yesterday}.json",
                    headers=headers
                )
                if sp02_response_yesterday.status_code == 200 and sp02_response_yesterday.json():
                    sp02_value = sp02_response_yesterday.json().get('value', {}).get('avg', "N/A")
                else:
                    logger.error(f"SpO2 fallback API error for {yesterday}: {sp02_response_yesterday.status_code} {sp02_response_yesterday.reason} for url: {sp02_response_yesterday.url}")
                logger.debug(f"SpO2 response for {today}: {sp02_response.json()}, fallback {yesterday}: {sp02_response_yesterday.json()}")

        # Fetch Heart Rate data
        heart_rate_response = requests.get(
            f"https://api.fitbit.com/1/user/-/activities/heart/date/{today}/1d/1m.json",
            headers=headers
        )
        heart_rate_value = "N/A"
        if heart_rate_response.status_code == 200 and heart_rate_response.json().get('activities-heart'):
            heart_rate_value = heart_rate_response.json()['activities-heart'][0].get('value', {}).get('restingHeartRate', "N/A")
        else:
            if heart_rate_response.status_code == 401:
                logger.error(f"Heart Rate API error for {today}: {heart_rate_response.status_code} {heart_rate_response.reason} for url: {heart_rate_response.url}")
                if self.refresh_access_token():
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    heart_rate_response = requests.get(
                        f"https://api.fitbit.com/1/user/-/activities/heart/date/{today}/1d/1m.json",
                        headers=headers
                    )
                    if heart_rate_response.status_code == 200 and heart_rate_response.json().get('activities-heart'):
                        heart_rate_value = heart_rate_response.json()['activities-heart'][0].get('value', {}).get('restingHeartRate', "N/A")
            if heart_rate_response.status_code != 200:
                # Try yesterday's data as a fallback
                heart_rate_response_yesterday = requests.get(
                    f"https://api.fitbit.com/1/user/-/activities/heart/date/{yesterday}/1d/1m.json",
                    headers=headers
                )
                if heart_rate_response_yesterday.status_code == 200 and heart_rate_response_yesterday.json().get('activities-heart'):
                    heart_rate_value = heart_rate_response_yesterday.json()['activities-heart'][0].get('value', {}).get('restingHeartRate', "N/A")
                else:
                    logger.error(f"Heart Rate fallback API error for {yesterday}: {heart_rate_response_yesterday.status_code} {heart_rate_response_yesterday.reason} for url: {heart_rate_response_yesterday.url}")
                logger.debug(f"Heart Rate response for {today}: {heart_rate_response.json()}, fallback {yesterday}: {heart_rate_response_yesterday.json()}")

        return {
            "sp02": sp02_value,
            "heart_rate": heart_rate_value
        }