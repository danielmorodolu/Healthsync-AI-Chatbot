import logging
from collections import defaultdict
import uuid
import time

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self):
        self.sessions = defaultdict(lambda: {
            "interview_id": str(uuid.uuid4()),
            "evidence": [],
            "last_question": None,
            "question_count": 0,
            "last_activity": time.time(),
            "age": 30,
            "sex": "male"
        })

    def get_session(self, user_id):
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
        logger.debug(f"Reset session for user_id: {user_id}")