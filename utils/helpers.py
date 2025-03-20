import logging
import os
import json
import time
import requests
from chatbot.config import ChatConfig

logger = logging.getLogger(__name__)

def setup_logging():
    """Sets up logging configuration."""
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    return logger

def load_cached_symptoms(cache_file=ChatConfig.CACHE_FILE, expiry=ChatConfig.CACHE_EXPIRY):
    """Loads cached symptom list if fresh."""
    if os.path.exists(cache_file):
        try:
            last_modified = os.path.getmtime(cache_file)
            if (time.time() - last_modified) < expiry:
                with open(cache_file, "r") as f:
                    cached_symptoms = json.load(f)
                    logger.debug(f"Loaded {len(cached_symptoms)} symptoms from {cache_file}")
                    return cached_symptoms
        except Exception as e:
            logger.error(f"Error loading cached symptoms: {str(e)}")
    return None

def fetch_symptoms(api_url, headers, params={"age.value": 30}):
    """Fetches and caches symptom list."""
    try:
        response = requests.get(f"{api_url}/symptoms", headers=headers, params=params)
        if response.status_code == 200:
            symptoms = {s["name"].lower(): s["id"] for s in response.json()}
            with open(ChatConfig.CACHE_FILE, "w") as f:
                json.dump(list(symptoms.items()), f)
            logger.debug(f"Fetched and cached {len(symptoms)} symptoms")
            return symptoms
        else:
            logger.error(f"Failed to fetch symptoms: {response.status_code}, {response.text}")
            return {}
    except Exception as e:
        logger.error(f"Error fetching symptoms: {str(e)}")
        return {}