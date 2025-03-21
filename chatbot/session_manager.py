import logging
from collections import defaultdict
import uuid
import time
import json
import os

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, storage_file="sessions.json"):
        self.storage_file = storage_file
        self.sessions = defaultdict(lambda: {
            "interview_id": str(uuid.uuid4()),
            "evidence": [],
            "last_question": None,
            "question_count": 0,
            "last_activity": time.time(),
            "age": 30,
            "sex": "male"
        })
        self._load_sessions()

    def _load_sessions(self):
        """Load sessions from the storage file if it exists."""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    loaded_sessions = json.load(f)
                    # Convert loaded sessions to defaultdict
                    for user_id, session_data in loaded_sessions.items():
                        self.sessions[user_id] = session_data
                logger.debug(f"Loaded sessions from {self.storage_file}: {self.sessions}")
            except Exception as e:
                logger.error(f"Error loading sessions from {self.storage_file}: {str(e)}")
                self.sessions = defaultdict(lambda: {
                    "interview_id": str(uuid.uuid4()),
                    "evidence": [],
                    "last_question": None,
                    "question_count": 0,
                    "last_activity": time.time(),
                    "age": 30,
                    "sex": "male"
                })

    def _save_sessions(self):
        """Save sessions to the storage file."""
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(dict(self.sessions), f)
            logger.debug(f"Saved sessions to {self.storage_file}")
        except Exception as e:
            logger.error(f"Error saving sessions to {self.storage_file}: {str(e)}")

    def get_session(self, user_id):
        logger.debug(f"Retrieving session for user_id: {user_id}, session: {self.sessions[user_id]}")
        return self.sessions[user_id]

    def reset_session(self, user_id):
        """Resets session data for a given user_id."""
        self.sessions[user_id] = {
            "interview_id": str(uuid.uuid4()),
            "evidence": [],
            "last_question": None,
            "question_count": 0,
            "last_activity": time.time(),
            "age": 30,
            "sex": "male"
        }
        self._save_sessions()
        logger.debug(f"Reset session for user_id: {user_id}, new session: {self.sessions[user_id]}")