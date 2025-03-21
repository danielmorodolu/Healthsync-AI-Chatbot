import logging
import requests
from datetime import datetime, timedelta
from decouple import config
import base64
from flask import session

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

    def get_basic_fitbit_data(self):
        """Fetch only SpO2 and heart rate for the chat page."""
        # Check if cached data exists and is recent
        if 'fitbit_basic_data' in session and 'fitbit_basic_timestamp' in session:
            timestamp = datetime.fromisoformat(session['fitbit_basic_timestamp'])
            if datetime.now() - timestamp < timedelta(minutes=15):
                logger.debug("Returning cached basic Fitbit data")
                return session['fitbit_basic_data']

        if not self.access_token:
            logger.error("No access token set for Fitbit API")
            return {"sp02": "N/A", "heart_rate": "N/A"}

        headers = {"Authorization": f"Bearer {self.access_token}"}
        today = datetime.now().strftime('%Y-%m-%d')
        one_week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        # Initialize return dictionary
        fitbit_data = {
            "sp02": "N/A",
            "heart_rate": "N/A"
        }

        # Fetch SpO2 data
        sp02_response = requests.get(
            f"https://api.fitbit.com/1/user/-/spo2/date/{today}.json",
            headers=headers
        )
        logger.debug(f"SpO2 response for {today}: {sp02_response.status_code} {sp02_response.text}")
        if sp02_response.status_code == 429:
            logger.error("Fitbit API rate limit exceeded for SpO2")
            return {"sp02": "Rate Limit Exceeded", "heart_rate": "Rate Limit Exceeded"}
        if sp02_response.status_code == 200 and sp02_response.json() and 'value' in sp02_response.json():
            fitbit_data["sp02"] = sp02_response.json()['value'].get('avg', "N/A")
        else:
            if sp02_response.status_code == 401:
                logger.error(f"SpO2 API error for {today}: {sp02_response.status_code} {sp02_response.reason} for url: {sp02_response.url}")
                if self.refresh_access_token():
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    sp02_response = requests.get(
                        f"https://api.fitbit.com/1/user/-/spo2/date/{today}.json",
                        headers=headers
                    )
                    logger.debug(f"SpO2 retry response for {today}: {sp02_response.status_code} {sp02_response.text}")
                    if sp02_response.status_code == 200 and sp02_response.json() and 'value' in sp02_response.json():
                        fitbit_data["sp02"] = sp02_response.json()['value'].get('avg', "N/A")
            if sp02_response.status_code != 200 or not sp02_response.json() or 'value' not in sp02_response.json():
                sp02_range_response = requests.get(
                    f"https://api.fitbit.com/1/user/-/spo2/date/{one_week_ago}/{today}.json",
                    headers=headers
                )
                logger.debug(f"SpO2 range response ({one_week_ago} to {today}): {sp02_range_response.status_code} {sp02_range_response.text}")
                if sp02_range_response.status_code == 429:
                    logger.error("Fitbit API rate limit exceeded for SpO2 range")
                    return {"sp02": "Rate Limit Exceeded", "heart_rate": "Rate Limit Exceeded"}
                if sp02_range_response.status_code == 200 and sp02_range_response.json():
                    for entry in reversed(sp02_range_response.json()):
                        if 'value' in entry and entry['value'].get('avg'):
                            fitbit_data["sp02"] = entry['value']['avg']
                            break

        # Fetch Heart Rate data
        heart_rate_response = requests.get(
            f"https://api.fitbit.com/1/user/-/activities/heart/date/{today}/1d/1m.json",
            headers=headers
        )
        logger.debug(f"Heart Rate response for {today}: {heart_rate_response.status_code} {heart_rate_response.text}")
        if heart_rate_response.status_code == 429:
            logger.error("Fitbit API rate limit exceeded for Heart Rate")
            return {"sp02": "Rate Limit Exceeded", "heart_rate": "Rate Limit Exceeded"}
        if heart_rate_response.status_code == 200 and heart_rate_response.json().get('activities-heart'):
            fitbit_data["heart_rate"] = heart_rate_response.json()['activities-heart'][0].get('value', {}).get('restingHeartRate', "N/A")
        else:
            if heart_rate_response.status_code == 401:
                logger.error(f"Heart Rate API error for {today}: {heart_rate_response.status_code} {heart_rate_response.reason} for url: {heart_rate_response.url}")
                if self.refresh_access_token():
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    heart_rate_response = requests.get(
                        f"https://api.fitbit.com/1/user/-/activities/heart/date/{today}/1d/1m.json",
                        headers=headers
                    )
                    logger.debug(f"Heart Rate retry response for {today}: {heart_rate_response.status_code} {heart_rate_response.text}")
                    if heart_rate_response.status_code == 200 and heart_rate_response.json().get('activities-heart'):
                        fitbit_data["heart_rate"] = heart_rate_response.json()['activities-heart'][0].get('value', {}).get('restingHeartRate', "N/A")
            if heart_rate_response.status_code != 200 or not heart_rate_response.json().get('activities-heart'):
                heart_rate_range_response = requests.get(
                    f"https://api.fitbit.com/1/user/-/activities/heart/date/{one_week_ago}/{today}.json",
                    headers=headers
                )
                logger.debug(f"Heart Rate range response ({one_week_ago} to {today}): {heart_rate_range_response.status_code} {heart_rate_range_response.text}")
                if heart_rate_range_response.status_code == 429:
                    logger.error("Fitbit API rate limit exceeded for Heart Rate range")
                    return {"sp02": "Rate Limit Exceeded", "heart_rate": "Rate Limit Exceeded"}
                if heart_rate_range_response.status_code == 200 and heart_rate_range_response.json():
                    for entry in reversed(heart_rate_range_response.json()['activities-heart']):
                        if 'value' in entry and entry['value'].get('restingHeartRate'):
                            fitbit_data["heart_rate"] = entry['value']['restingHeartRate']
                            break

        # Cache the data
        session['fitbit_basic_data'] = fitbit_data
        session['fitbit_basic_timestamp'] = datetime.now().isoformat()
        return fitbit_data

    def get_all_fitbit_data(self):
        """Fetch all available Fitbit metrics for the health dashboard."""
        # Check if cached data exists and is recent
        if 'fitbit_all_data' in session and 'fitbit_all_timestamp' in session:
            timestamp = datetime.fromisoformat(session['fitbit_all_timestamp'])
            if datetime.now() - timestamp < timedelta(minutes=15):
                logger.debug("Returning cached all Fitbit data")
                return session['fitbit_all_data']

        if not self.access_token:
            logger.error("No access token set for Fitbit API")
            return {
                "sp02": "N/A",
                "heart_rate": "N/A",
                "heart_rate_zones": {
                    "out_of_range": {"caloriesOut": "N/A", "minutes": "N/A"},
                    "fat_burn": {"caloriesOut": "N/A", "minutes": "N/A"},
                    "cardio": {"caloriesOut": "N/A", "minutes": "N/A"},
                    "peak": {"caloriesOut": "N/A", "minutes": "N/A"}
                },
                "steps": "N/A",
                "distance": "N/A",
                "calories": "N/A",
                "active_minutes": "N/A",
                "floors": "N/A",
                "sleep_duration": "N/A",
                "sleep_stages": {"light": "N/A", "deep": "N/A", "rem": "N/A", "wake": "N/A"},
                "weight": "N/A",
                "bmi": "N/A",
                "body_fat": "N/A",
                "water": "N/A",
                "calories_in": "N/A"
            }

        headers = {"Authorization": f"Bearer {self.access_token}"}
        today = datetime.now().strftime('%Y-%m-%d')
        one_week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        # Initialize return dictionary
        fitbit_data = {
            "sp02": "N/A",
            "heart_rate": "N/A",
            "heart_rate_zones": {
                "out_of_range": {"caloriesOut": "N/A", "minutes": "N/A"},
                "fat_burn": {"caloriesOut": "N/A", "minutes": "N/A"},
                "cardio": {"caloriesOut": "N/A", "minutes": "N/A"},
                "peak": {"caloriesOut": "N/A", "minutes": "N/A"}
            },
            "steps": "N/A",
            "distance": "N/A",
            "calories": "N/A",
            "active_minutes": "N/A",
            "floors": "N/A",
            "sleep_duration": "N/A",
            "sleep_stages": {"light": "N/A", "deep": "N/A", "rem": "N/A", "wake": "N/A"},
            "weight": "N/A",
            "bmi": "N/A",
            "body_fat": "N/A",
            "water": "N/A",
            "calories_in": "N/A"
        }

        # Fetch SpO2 data
        sp02_response = requests.get(
            f"https://api.fitbit.com/1/user/-/spo2/date/{today}.json",
            headers=headers
        )
        logger.debug(f"SpO2 response for {today}: {sp02_response.status_code} {sp02_response.text}")
        if sp02_response.status_code == 429:
            logger.error("Fitbit API rate limit exceeded for SpO2")
            return {key: "Rate Limit Exceeded" for key in fitbit_data}
        if sp02_response.status_code == 200 and sp02_response.json() and 'value' in sp02_response.json():
            fitbit_data["sp02"] = sp02_response.json()['value'].get('avg', "N/A")
        else:
            if sp02_response.status_code == 401:
                logger.error(f"SpO2 API error for {today}: {sp02_response.status_code} {sp02_response.reason} for url: {sp02_response.url}")
                if self.refresh_access_token():
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    sp02_response = requests.get(
                        f"https://api.fitbit.com/1/user/-/spo2/date/{today}.json",
                        headers=headers
                    )
                    logger.debug(f"SpO2 retry response for {today}: {sp02_response.status_code} {sp02_response.text}")
                    if sp02_response.status_code == 200 and sp02_response.json() and 'value' in sp02_response.json():
                        fitbit_data["sp02"] = sp02_response.json()['value'].get('avg', "N/A")
            if sp02_response.status_code != 200 or not sp02_response.json() or 'value' not in sp02_response.json():
                sp02_range_response = requests.get(
                    f"https://api.fitbit.com/1/user/-/spo2/date/{one_week_ago}/{today}.json",
                    headers=headers
                )
                logger.debug(f"SpO2 range response ({one_week_ago} to {today}): {sp02_range_response.status_code} {sp02_range_response.text}")
                if sp02_range_response.status_code == 429:
                    logger.error("Fitbit API rate limit exceeded for SpO2 range")
                    return {key: "Rate Limit Exceeded" for key in fitbit_data}
                if sp02_range_response.status_code == 200 and sp02_range_response.json():
                    for entry in reversed(sp02_range_response.json()):
                        if 'value' in entry and entry['value'].get('avg'):
                            fitbit_data["sp02"] = entry['value']['avg']
                            break

        # Fetch Heart Rate data (including zones)
        heart_rate_response = requests.get(
            f"https://api.fitbit.com/1/user/-/activities/heart/date/{today}/1d/1m.json",
            headers=headers
        )
        logger.debug(f"Heart Rate response for {today}: {heart_rate_response.status_code} {heart_rate_response.text}")
        if heart_rate_response.status_code == 429:
            logger.error("Fitbit API rate limit exceeded for Heart Rate")
            return {key: "Rate Limit Exceeded" for key in fitbit_data}
        if heart_rate_response.status_code == 200 and heart_rate_response.json().get('activities-heart'):
            fitbit_data["heart_rate"] = heart_rate_response.json()['activities-heart'][0].get('value', {}).get('restingHeartRate', "N/A")
            heart_rate_zones = heart_rate_response.json()['activities-heart'][0].get('value', {}).get('heartRateZones', [])
            for zone in heart_rate_zones:
                zone_name = zone['name'].lower().replace(" ", "_")
                fitbit_data["heart_rate_zones"][zone_name] = {
                    "caloriesOut": zone.get('caloriesOut', "N/A"),
                    "minutes": zone.get('minutes', "N/A")
                }
        else:
            if heart_rate_response.status_code == 401:
                logger.error(f"Heart Rate API error for {today}: {heart_rate_response.status_code} {heart_rate_response.reason} for url: {heart_rate_response.url}")
                if self.refresh_access_token():
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    heart_rate_response = requests.get(
                        f"https://api.fitbit.com/1/user/-/activities/heart/date/{today}/1d/1m.json",
                        headers=headers
                    )
                    logger.debug(f"Heart Rate retry response for {today}: {heart_rate_response.status_code} {heart_rate_response.text}")
                    if heart_rate_response.status_code == 200 and heart_rate_response.json().get('activities-heart'):
                        fitbit_data["heart_rate"] = heart_rate_response.json()['activities-heart'][0].get('value', {}).get('restingHeartRate', "N/A")
                        heart_rate_zones = heart_rate_response.json()['activities-heart'][0].get('value', {}).get('heartRateZones', [])
                        for zone in heart_rate_zones:
                            zone_name = zone['name'].lower().replace(" ", "_")
                            fitbit_data["heart_rate_zones"][zone_name] = {
                                "caloriesOut": zone.get('caloriesOut', "N/A"),
                                "minutes": zone.get('minutes', "N/A")
                            }
            if heart_rate_response.status_code != 200 or not heart_rate_response.json().get('activities-heart'):
                heart_rate_range_response = requests.get(
                    f"https://api.fitbit.com/1/user/-/activities/heart/date/{one_week_ago}/{today}.json",
                    headers=headers
                )
                logger.debug(f"Heart Rate range response ({one_week_ago} to {today}): {heart_rate_range_response.status_code} {heart_rate_range_response.text}")
                if heart_rate_range_response.status_code == 429:
                    logger.error("Fitbit API rate limit exceeded for Heart Rate range")
                    return {key: "Rate Limit Exceeded" for key in fitbit_data}
                if heart_rate_range_response.status_code == 200 and heart_rate_range_response.json():
                    for entry in reversed(heart_rate_range_response.json()['activities-heart']):
                        if 'value' in entry and entry['value'].get('restingHeartRate'):
                            fitbit_data["heart_rate"] = entry['value']['restingHeartRate']
                            heart_rate_zones = entry['value'].get('heartRateZones', [])
                            for zone in heart_rate_zones:
                                zone_name = zone['name'].lower().replace(" ", "_")
                                fitbit_data["heart_rate_zones"][zone_name] = {
                                    "caloriesOut": zone.get('caloriesOut', "N/A"),
                                    "minutes": zone.get('minutes', "N/A")
                                }
                            break

        # Fetch Activity data (steps, distance, calories, active minutes, floors)
        activity_response = requests.get(
            f"https://api.fitbit.com/1/user/-/activities/date/{today}.json",
            headers=headers
        )
        logger.debug(f"Activity response for {today}: {activity_response.status_code} {activity_response.text}")
        if activity_response.status_code == 429:
            logger.error("Fitbit API rate limit exceeded for Activity")
            return {key: "Rate Limit Exceeded" for key in fitbit_data}
        if activity_response.status_code == 200 and activity_response.json():
            summary = activity_response.json().get('summary', {})
            fitbit_data["steps"] = summary.get('steps', "N/A")
            fitbit_data["distance"] = summary.get('distances', [{}])[0].get('distance', "N/A")
            fitbit_data["calories"] = summary.get('caloriesOut', "N/A")
            fitbit_data["active_minutes"] = summary.get('fairlyActiveMinutes', 0) + summary.get('veryActiveMinutes', 0)
            fitbit_data["floors"] = summary.get('floors', "N/A")

        # Fetch Sleep data
        sleep_response = requests.get(
            f"https://api.fitbit.com/1.2/user/-/sleep/date/{today}.json",
            headers=headers
        )
        logger.debug(f"Sleep response for {today}: {sleep_response.status_code} {sleep_response.text}")
        if sleep_response.status_code == 429:
            logger.error("Fitbit API rate limit exceeded for Sleep")
            return {key: "Rate Limit Exceeded" for key in fitbit_data}
        if sleep_response.status_code == 200 and sleep_response.json().get('sleep'):
            sleep_data = sleep_response.json()['sleep'][0] if sleep_response.json()['sleep'] else {}
            fitbit_data["sleep_duration"] = sleep_data.get('duration', "N/A") / 60000 if sleep_data.get('duration') else "N/A"  # Convert milliseconds to minutes
            if 'levels' in sleep_data and 'summary' in sleep_data['levels']:
                levels = sleep_data['levels']['summary']
                fitbit_data["sleep_stages"] = {
                    "light": levels.get('light', {}).get('minutes', "N/A"),
                    "deep": levels.get('deep', {}).get('minutes', "N/A"),
                    "rem": levels.get('rem', {}).get('minutes', "N/A"),
                    "wake": levels.get('wake', {}).get('minutes', "N/A")
                }
        else:
            sleep_range_response = requests.get(
                f"https://api.fitbit.com/1.2/user/-/sleep/date/{one_week_ago}/{today}.json",
                headers=headers
            )
            logger.debug(f"Sleep range response ({one_week_ago} to {today}): {sleep_range_response.status_code} {sleep_range_response.text}")
            if sleep_range_response.status_code == 429:
                logger.error("Fitbit API rate limit exceeded for Sleep range")
                return {key: "Rate Limit Exceeded" for key in fitbit_data}
            if sleep_range_response.status_code == 200 and sleep_range_response.json().get('sleep'):
                sleep_data = sleep_range_response.json()['sleep'][0] if sleep_range_response.json()['sleep'] else {}
                fitbit_data["sleep_duration"] = sleep_data.get('duration', "N/A") / 60000 if sleep_data.get('duration') else "N/A"
                if 'levels' in sleep_data and 'summary' in sleep_data['levels']:
                    levels = sleep_data['levels']['summary']
                    fitbit_data["sleep_stages"] = {
                        "light": levels.get('light', {}).get('minutes', "N/A"),
                        "deep": levels.get('deep', {}).get('minutes', "N/A"),
                        "rem": levels.get('rem', {}).get('minutes', "N/A"),
                        "wake": levels.get('wake', {}).get('minutes', "N/A")
                    }

        # Fetch Weight data
        weight_response = requests.get(
            f"https://api.fitbit.com/1/user/-/body/log/weight/date/{today}.json",
            headers=headers
        )
        logger.debug(f"Weight response for {today}: {weight_response.status_code} {weight_response.text}")
        if weight_response.status_code == 429:
            logger.error("Fitbit API rate limit exceeded for Weight")
            return {key: "Rate Limit Exceeded" for key in fitbit_data}
        if weight_response.status_code == 200 and weight_response.json().get('weight'):
            weight_data = weight_response.json()['weight'][0] if weight_response.json()['weight'] else {}
            fitbit_data["weight"] = weight_data.get('weight', "N/A")
            fitbit_data["bmi"] = weight_data.get('bmi', "N/A")
            fitbit_data["body_fat"] = weight_data.get('fat', "N/A")
        else:
            weight_range_response = requests.get(
                f"https://api.fitbit.com/1/user/-/body/log/weight/date/{one_week_ago}/{today}.json",
                headers=headers
            )
            logger.debug(f"Weight range response ({one_week_ago} to {today}): {weight_range_response.status_code} {weight_range_response.text}")
            if weight_range_response.status_code == 429:
                logger.error("Fitbit API rate limit exceeded for Weight range")
                return {key: "Rate Limit Exceeded" for key in fitbit_data}
            if weight_range_response.status_code == 200 and weight_range_response.json().get('weight'):
                weight_data = weight_range_response.json()['weight'][0] if weight_range_response.json()['weight'] else {}
                fitbit_data["weight"] = weight_data.get('weight', "N/A")
                fitbit_data["bmi"] = weight_data.get('bmi', "N/A")
                fitbit_data["body_fat"] = weight_data.get('fat', "N/A")

        # Fetch Nutrition data (food and water)
        food_response = requests.get(
            f"https://api.fitbit.com/1/user/-/foods/log/date/{today}.json",
            headers=headers
        )
        logger.debug(f"Food response for {today}: {food_response.status_code} {food_response.text}")
        if food_response.status_code == 429:
            logger.error("Fitbit API rate limit exceeded for Food")
            return {key: "Rate Limit Exceeded" for key in fitbit_data}
        if food_response.status_code == 200 and food_response.json().get('summary'):
            fitbit_data["calories_in"] = food_response.json()['summary'].get('calories', "N/A")

        water_response = requests.get(
            f"https://api.fitbit.com/1/user/-/foods/log/water/date/{today}.json",
            headers=headers
        )
        logger.debug(f"Water response for {today}: {water_response.status_code} {water_response.text}")
        if water_response.status_code == 429:
            logger.error("Fitbit API rate limit exceeded for Water")
            return {key: "Rate Limit Exceeded" for key in fitbit_data}
        if water_response.status_code == 200 and water_response.json().get('summary'):
            fitbit_data["water"] = water_response.json()['summary'].get('water', "N/A")  # In milliliters

        # Cache the data
        session['fitbit_all_data'] = fitbit_data
        session['fitbit_all_timestamp'] = datetime.now().isoformat()
        return fitbit_data