import logging
import requests
import json
from openai import OpenAI
import httpx  # Added import for custom HTTP client
import uuid
from decouple import config
from chatbot.config import ChatConfig

logger = logging.getLogger(__name__)

class InfermedicaClient:
    def __init__(self):
        self.api_url = "https://api.infermedica.com/v3"
        self.app_id = config("INFERMEDICA_APP_ID")
        self.app_key = config("INFERMEDICA_APP_KEY")
        self.headers = {
            "App-Id": self.app_id,
            "App-Key": self.app_key,
            "Content-Type": "application/json"
        }
        # Initialize OpenAI client with a custom HTTP client
        http_client = httpx.Client()
        self.client = OpenAI(api_key=config("OPENAI_API_KEY"), http_client=http_client)

    def get_diagnosis(self, evidence, age=30, sex="male", interview_id=str(uuid.uuid4())):
        """Calls Infermedica /diagnosis."""
        payload = {
            "sex": sex,
            "age": {"value": age},
            "evidence": evidence,
            "interview_id": interview_id
        }
        try:
            response = requests.post(f"{self.api_url}/diagnosis", json=payload, headers=self.headers)
            logger.debug(f"Diagnosis response: {response.text}")
            return response.json() if response.status_code == 200 else {"error": f"API error: {response.status_code}"}
        except Exception as e:
            logger.error(f"Infermedica diagnosis error: {str(e)}")
            return {"error": str(e)}

    def get_triage(self, evidence, age=30, sex="male"):
        """Calls Infermedica /triage."""
        if not evidence:
            return {"triage_level": "unknown", "message": "We are still assessing your condition."}

        payload = {"sex": sex, "age": {"value": age}, "evidence": evidence, "interview_id": str(uuid.uuid4())}
        try:
            response = requests.post(f"{self.api_url}/triage", json=payload, headers=self.headers)
            if response.status_code == 200:
                triage_data = response.json()
                triage_level = triage_data.get("triage_level", "unknown")
                triage_messages = {
                    "emergency": "Seek immediate medical attention.",
                    "consultation": "Schedule an appointment with a doctor within 24 hours.",
                    "self_care": "You can manage this at home with rest and hydration. Contact a doctor if symptoms worsen."
                }
                return {
                    "triage_level": triage_level,
                    "message": triage_messages.get(triage_level, "We are still assessing your condition.")
                }
            return {"triage_level": "unknown", "message": "We are still assessing your condition."}
        except Exception as e:
            logger.error(f"Infermedica triage error: {str(e)}")
            return {"triage_level": "unknown", "message": "We are still assessing your condition."}

    def is_yes_no_question(self, question_text):
        """Classifies if a question is yes/no using OpenAI."""
        prompt = f"Is this a yes/no question? Respond with 'yes' or 'no'. Question: '{question_text}'"
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5,
                temperature=0.0
            )
            answer = response.choices[0].message.content.strip().lower()
            return answer == "yes"
        except Exception as e:
            logger.error(f"Error in yes/no detection: {str(e)}")
            return False

    def format_response(self, conditions, triage_data, is_final=False):
        """Formats diagnosis and triage response."""
        if not conditions:
            return "I couldn't determine a specific condition yet. Let's continue diagnosing."

        conditions = sorted(conditions, key=lambda c: c["probability"], reverse=True)
        primary_condition = conditions[0]
        other_conditions = [c for c in conditions[1:3] if (primary_condition["probability"] - c["probability"]) <= ChatConfig.PROBABILITY_DIFF_THRESHOLD]

        triage_messages = {
            "emergency": "Seek immediate medical attention.",
            "consultation_24": "It is recommended that you see a doctor **within 24 hours**.",
            "consultation": "You should consult a doctor soon.",
            "self_care": "You can manage this at home, but monitor your symptoms closely.",
            "unknown": "We are still assessing your condition."
        }
        triage_text = triage_messages.get(triage_data["triage_level"], "We are still assessing your condition.")

        response = f"The most likely condition is **{primary_condition['name']} (likelihood: {primary_condition['probability']*100:.1f}%)**."
        if other_conditions:
            response += " Other possible conditions include: " + ", ".join(
                f"{c['name']} (likelihood: {c['probability']*100:.1f}%)" for c in other_conditions
            ) + "."
        
        response += f" **Triage Recommendation:** {triage_text}"
        return response