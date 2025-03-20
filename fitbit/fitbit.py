import logging
import requests
import time
from decouple import config

logger = logging.getLogger(__name__)

class FitbitClient:
    def __init__(self):
        self.api_url = "https://api.fitbit.com/1/user/-/"
        self.access_token = None

    def set_access_token(self, token):
        self.access_token = token

    def get_fitbit_data(self):
        if not self.access_token:
            logger.warning("No access token in session")
            return {"sp02": "N/A", "heart_rate": "N/A"}

        headers = {"Authorization": f"Bearer {self.access_token}"}
        today = time.strftime("%Y-%m-%d")
        yesterday = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 86400))
        result = {"sp02": "N/A", "heart_rate": "N/A"}

        # Fetch SpO2 data for today, fallback to yesterday if unavailable
        try:
            sp02_response = requests.get(f"{self.api_url}spo2/date/{today}.json", headers=headers)
            sp02_response.raise_for_status()
            sp02_data = sp02_response.json()
            if sp02_data and "value" in sp02_data and sp02_data["value"].get("avg") is not None:
                result["sp02"] = sp02_data["value"]["avg"]
            else:
                sp02_response_yesterday = requests.get(f"{self.api_url}spo2/date/{yesterday}.json", headers=headers)
                sp02_response_yesterday.raise_for_status()
                sp02_data_yesterday = sp02_response_yesterday.json()
                if sp02_data_yesterday and "value" in sp02_data_yesterday and sp02_data_yesterday["value"].get("avg") is not None:
                    result["sp02"] = sp02_data_yesterday["value"]["avg"]
            logger.debug(f"SpO2 response for {today}: {sp02_response.json()}, fallback {yesterday}: {sp02_response_yesterday.json()}")
        except requests.exceptions.RequestException as e:
            logger.error(f"SpO2 API error for {today}: {str(e)}")
            try:
                sp02_response_yesterday = requests.get(f"{self.api_url}spo2/date/{yesterday}.json", headers=headers)
                sp02_response_yesterday.raise_for_status()
                sp02_data_yesterday = sp02_response_yesterday.json()
                if sp02_data_yesterday and "value" in sp02_data_yesterday and sp02_data_yesterday["value"].get("avg") is not None:
                    result["sp02"] = sp02_data_yesterday["value"]["avg"]
                logger.debug(f"SpO2 fallback response for {yesterday}: {sp02_response_yesterday.json()}")
            except requests.exceptions.RequestException as e_fallback:
                logger.error(f"SpO2 fallback API error for {yesterday}: {str(e_fallback)}")
                result["sp02"] = "N/A"

        # Fetch heart rate intraday data for today, fallback to yesterday if unavailable
        try:
            hr_response = requests.get(f"{self.api_url}activities/heart/date/{today}/1d/1m.json", headers=headers)
            hr_response.raise_for_status()
            hr_data = hr_response.json().get("activities-heart-intraday", {}).get("dataset", [])
            hr_value = hr_data[-1].get("value", "N/A") if hr_data else "N/A"
            if hr_value == "N/A" and not hr_data:
                hr_response_yesterday = requests.get(f"{self.api_url}activities/heart/date/{yesterday}/1d/1m.json", headers=headers)
                hr_response_yesterday.raise_for_status()
                hr_data_yesterday = hr_response_yesterday.json().get("activities-heart-intraday", {}).get("dataset", [])
                hr_value_yesterday = hr_data_yesterday[-1].get("value", "N/A") if hr_data_yesterday else "N/A"
                result["heart_rate"] = hr_value_yesterday if hr_value_yesterday != "N/A" else "N/A"
            else:
                result["heart_rate"] = hr_value
            logger.debug(f"Heart Rate response for {today}: {hr_response.json()}, fallback {yesterday}: {hr_response_yesterday.json() if 'hr_response_yesterday' in locals() else 'Not attempted'}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Heart Rate API error for {today}: {str(e)}")
            try:
                hr_response_yesterday = requests.get(f"{self.api_url}activities/heart/date/{yesterday}/1d/1m.json", headers=headers)
                hr_response_yesterday.raise_for_status()
                hr_data_yesterday = hr_response_yesterday.json().get("activities-heart-intraday", {}).get("dataset", [])
                hr_value_yesterday = hr_data_yesterday[-1].get("value", "N/A") if hr_data_yesterday else "N/A"
                result["heart_rate"] = hr_value_yesterday if hr_value_yesterday != "N/A" else "N/A"
                logger.debug(f"Heart Rate fallback response for {yesterday}: {hr_response_yesterday.json()}")
            except requests.exceptions.RequestException as e_fallback:
                logger.error(f"Heart Rate fallback API error for {yesterday}: {str(e_fallback)}")
                result["heart_rate"] = "N/A"

        return result