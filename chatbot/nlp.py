import logging
import re
from fuzzywuzzy import process
from openai import OpenAI
import requests
import json
import httpx
from decouple import config
from chatbot.config import ChatConfig

logger = logging.getLogger(__name__)

class NLPProcessor:
    def __init__(self):
        # Initialize OpenAI client with a custom HTTP client
        http_client = httpx.Client()
        self.client = OpenAI(api_key=config("OPENAI_API_KEY"), http_client=http_client)
        self.symptom_map = {}
        self.infermedica_api_url = config('INFERMEDICA_API_URL', default='https://api.infermedica.com/v3')
        self.infermedica_headers = {
            "App-Id": config("INFERMEDICA_APP_ID"),
            "App-Key": config("INFERMEDICA_APP_KEY"),
            "Content-Type": "application/json"
        }
        # Manual symptom mapping for common symptoms (fallback when Infermedica fails)
        self.manual_symptom_mapping = {
            "itching": "s_192",  # Itching or burning skin
            "redness": "s_208",  # Skin redness
            "swelling": "s_223",  # Swelling
            "fever": "s_98",     # Fever
            "fatigue": "s_6",    # Fatigue
            "pain": "s_1849",    # Pain, general
            "rash": "s_2582"     # Rash (already mapped in previous logs)
        }

    def load_symptom_map(self, symptom_map):
        self.symptom_map = symptom_map

    def classify_intent(self, user_input):
        """Classifies input intent as 'medical' or 'general'."""
        user_input = re.sub(r'([a-z])([A-Z])', r'\1 \2', user_input).lower().strip()
        prompt = f"Classify the intent of this input as 'medical' (symptom report or health-related) or 'general' (non-medical): '{user_input}'"
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Respond with 'medical' or 'general'."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10
            )
            intent = response.choices[0].message.content.strip().lower()
            logger.debug(f"Classified intent: {intent}")
            return intent
        except Exception as e:
            logger.error(f"Intent classification error: {str(e)}")
            return "medical"

    def interpret_vague_symptoms(self, user_input):
        """Interprets vague symptom descriptions using GPT-4."""
        user_input = re.sub(r'([a-z])([A-Z])', r'\1 \2', user_input).lower().strip()
        prompt = f"""
        The user has provided a vague symptom description: '{user_input}'. 
        Interpret this description and suggest likely medical symptoms that could be associated with it.
        Return a list of symptoms in JSON format, e.g., {{"symptoms": ["fever", "fatigue"]}}.
        If the input is too vague to determine specific symptoms, return {{"symptoms": []}}.
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a medical assistant. Respond with JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100
            )
            result = json.loads(response.choices[0].message.content.strip())
            logger.debug(f"Interpreted vague symptoms: {result}")
            return result.get("symptoms", [])
        except Exception as e:
            logger.error(f"Error interpreting vague symptoms: {str(e)}")
            return []

    def map_symptom_to_infermedica(self, symptom_text, age=30, sex="male"):
        """Maps a symptom description to an Infermedica symptom ID using the /suggest endpoint."""
        symptom_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', symptom_text).lower().strip()
        payload = {
            "text": symptom_text,
            "age": {"value": age},
            "sex": sex,
            "limit": 1  # Get the top suggestion
        }
        try:
            response = requests.post(f"{self.infermedica_api_url}/suggest", json=payload, headers=self.infermedica_headers)
            if response.status_code == 200:
                data = response.json()
                if data and isinstance(data, list) and len(data) > 0:
                    suggestion = data[0]
                    symptom_id = suggestion.get("id")
                    if symptom_id:
                        logger.debug(f"Mapped symptom '{symptom_text}' to Infermedica ID: {symptom_id}")
                        return symptom_id
                logger.warning(f"No Infermedica suggestion found for symptom: {symptom_text}")
            else:
                logger.warning(f"Infermedica /suggest failed: {response.status_code}, {response.text}")
        except Exception as e:
            logger.error(f"Infermedica suggest error for symptom '{symptom_text}': {str(e)}")
        return None

    def parse_symptoms_infermedica(self, user_input, age=30, sex="male"):
        """Extracts symptoms using Infermedica /parse with fallback."""
        user_input = re.sub(r'([a-z])([A-Z])', r'\1 \2', user_input).lower().strip()
        payload = {"text": user_input, "age": {"value": age}, "sex": sex}
        try:
            response = requests.post(f"{self.infermedica_api_url}/parse", json=payload, headers=self.infermedica_headers)
            logger.debug(f"Calling Infermedica /parse with URL: {response.url}")
            if response.status_code == 200:
                data = response.json()
                mentions = data.get("mentions", [])
                symptoms = [{"id": m["id"], "choice_id": m["choice_id"]} for m in mentions]
                logger.debug(f"Parsed symptoms: {symptoms}")
                if symptoms:
                    return symptoms
            logger.warning(f"Parse failed or no symptoms found: {response.status_code}, {response.text}")
        except Exception as e:
            logger.error(f"Infermedica parse error: {str(e)}")

        possible_symptoms = self.interpret_vague_symptoms(user_input)
        if not possible_symptoms:
            return []

        symptoms = []
        for symptom in possible_symptoms:
            symptom_lower = symptom.lower()
            # First, check if the symptom is in SYMPTOM_MAP
            if symptom_lower in self.symptom_map:
                symptoms.append({"id": self.symptom_map[symptom_lower], "choice_id": "present"})
            else:
                # Try Infermedica /suggest
                symptom_id = self.map_symptom_to_infermedica(symptom, age, sex)
                if symptom_id:
                    symptoms.append({"id": symptom_id, "choice_id": "present"})
                else:
                    # Fallback to manual mapping
                    if symptom_lower in self.manual_symptom_mapping:
                        symptom_id = self.manual_symptom_mapping[symptom_lower]
                        symptoms.append({"id": symptom_id, "choice_id": "present"})
                        logger.debug(f"Manually mapped symptom '{symptom_lower}' to ID: {symptom_id}")
                    else:
                        logger.warning(f"Symptom '{symptom}' could not be mapped to an Infermedica ID")
        return symptoms

    def parse_duration_answer(self, user_input, question_text, last_question):
        """Parses duration answers using regex or GPT-4."""
        user_input = re.sub(r'([a-z])([A-Z])', r'\1 \2', user_input).lower().strip()
        duration_pattern = r"(\d+)\s*(year|years|month|months|day|days|hour|hours|week|weeks)"
        match = re.search(duration_pattern, user_input)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            choice_id = "present" if value > 0 else "absent"
            return [{"id": last_question[0]["id"], "choice_id": choice_id}]
        prompt = f"Interpret this duration answer for the question: '{question_text}'. Text: '{user_input}'. Return JSON: {{'value': number, 'unit': 'year/month/day/hour/week'}} or null if unclear."
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Respond with JSON or null."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50
            )
            parsed = json.loads(response.choices[0].message.content.strip() or "null")
            if parsed and "value" in parsed and "unit" in parsed:
                choice_id = "present" if parsed["value"] > 0 else "absent"
                return [{"id": last_question[0]["id"], "choice_id": choice_id}]
            return []
        except Exception as e:
            logger.error(f"Duration parsing error: {str(e)}")
            return []

    def parse_free_text_answer(self, user_input, question_items, question_text):
        """Parses free-text answers with negation handling."""
        user_input = re.sub(r'([a-z])([A-Z])', r'\1 \2', user_input).lower().strip()
        negation_pattern = r"(don't have|no|not|haven't|didn't)\s*(.+)"
        match = re.search(negation_pattern, user_input)
        if match:
            negated_symptom = match.group(2).strip()
            for item in question_items:
                if negated_symptom in item["name"].lower():
                    return [{"id": item["id"], "choice_id": "absent"}]

        prompt = f"Interpret this free-text answer for the question: '{question_text}'. Text: '{user_input}'. Return JSON: {{'item': 'item_name', 'choice': 'yes/no/don’t know'}} or null if unclear."
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Respond with JSON or null."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50
            )
            parsed_answer = json.loads(response.choices[0].message.content.strip() or "null")
            if parsed_answer and "item" in parsed_answer and "choice" in parsed_answer:
                item_name = parsed_answer["item"].lower()
                choice = parsed_answer["choice"].lower()
                for item in question_items:
                    if item["name"].lower() == item_name:
                        return [{"id": item["id"], "choice_id": {"yes": "present", "no": "absent", "don't know": "unknown"}[choice]}]
            return []
        except Exception as e:
            logger.error(f"GPT free-text parsing error: {str(e)}")
            return []