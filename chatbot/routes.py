import logging
from flask import request, jsonify, render_template, session, redirect, url_for
from openai import OpenAI
import time
import json
from decouple import config
import httpx
from fuzzywuzzy import process
from chatbot.session_manager import SessionManager
from chatbot.infermedica import InfermedicaClient
from chatbot.nlp import NLPProcessor
from fitbit.fitbit import FitbitClient
from utils.helpers import load_cached_symptoms
from chatbot.config import ChatConfig

logger = logging.getLogger(__name__)

# Initialize OpenAI client with a custom HTTP client
http_client = httpx.Client()
client = OpenAI(api_key=config("OPENAI_API_KEY"), http_client=http_client)

class ChatRoutes:
    def __init__(self, app, session_manager, infermedica_client, nlp_processor, fitbit_client, symptom_map):
        self.app = app
        self.session_manager = session_manager
        self.infermedica_client = infermedica_client
        self.nlp_processor = nlp_processor
        self.fitbit_client = fitbit_client
        self.symptom_map = symptom_map

        # Define routes with unique endpoint names
        self.app.route('/chat', methods=['GET'], endpoint='chat_get')(self.chat_get)
        self.app.route('/chat', methods=['POST'], endpoint='chat_post')(self.chat_post)
        self.app.route('/reset', methods=['POST'])(self.reset)
        self.app.route('/symptoms', methods=['GET'])(self.get_symptoms)
        self.app.route('/feedback', methods=['POST'])(self.feedback)
        self.app.route('/debug/token', methods=['GET'])(self.debug_token)

    def chat_get(self):
        if 'auth0_user' not in session and 'fitbit_user' not in session:
            return redirect(url_for('index'))

        user_id = session.get('user_id', 'default')
        user_session = self.session_manager.get_session(user_id)
        smartwatch_data = None
        if 'fitbit_user' in session and session.get('access_token'):
            self.fitbit_client.set_access_token(session.get('access_token'))
            self.fitbit_client.set_refresh_token(session.get('refresh_token'))
            smartwatch_data = self.fitbit_client.get_basic_fitbit_data()
            logger.debug(f"Smartwatch Data: {smartwatch_data}")
        else:
            # Clear any invalid Fitbit-related session data if the user is not logged in with Fitbit
            if 'fitbit_user' in session:
                session.pop('fitbit_user', None)
            if 'access_token' in session:
                session.pop('access_token', None)
            if 'refresh_token' in session:
                session.pop('refresh_token', None)
            smartwatch_data = {
                "sp02": "N/A",
                "heart_rate": "N/A"
            }

        # Check if health data exists
        has_health_data = bool(user_session.get('manual_health_data', {}))

        return render_template(
            'chat.html',
            user_id=user_id,
            fitbit_user='fitbit_user' in session,
            smartwatch_data=smartwatch_data,
            messages=[],
            age=user_session.get('age'),
            sex=user_session.get('sex'),
            has_health_data=has_health_data
        )

    def chat_post(self):
        try:
            data = request.get_json()
            if not data:
                logger.error("No JSON data received in request")
                return jsonify({"message": "Invalid request: No JSON data provided.", "follow_up": "", "user_input": ""}), 400

            user_input = data.get('input', '')
            user_id = data.get('user_id', 'default')
            answer = data.get('answer', '')
            free_text = data.get('free_text', '')
            age = int(data.get('age', 30))
            sex = data.get('sex', 'male')

            # Debug: Log the received data
            logger.debug(f"Received POST data: {data}")

            # Validate age (backend check)
            if age < 18:
                return jsonify({
                    "message": "This application is for users aged 18 and above.",
                    "error_message": "This application is for users aged 18 and above. Please consult a pediatrician for children.",
                    "follow_up": "",
                    "user_input": user_input
                })

            if not user_input and not answer and not free_text:
                return jsonify({"message": "No input, answer, or description provided.", "follow_up": "", "user_input": user_input})

            user_session = self.session_manager.get_session(user_id)
            user_session["last_activity"] = time.time()
            user_session["age"] = age
            user_session["sex"] = sex
            self.session_manager._save_sessions()  # Save after updating session

            # Step 1: Process Initial Symptoms
            if user_input:
                intent = self.nlp_processor.classify_intent(user_input)
                if intent == "general":
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": f"Answer this general question: {user_input}"}
                        ],
                        max_tokens=100
                    )
                    return jsonify({"message": response.choices[0].message.content.strip(), "follow_up": "", "user_input": user_input})

                if user_session.get("evidence") and user_session.get("question_count", 0) > 0:
                    self.session_manager.reset_session(user_id)
                    user_session = self.session_manager.get_session(user_id)

                symptoms = self.nlp_processor.parse_symptoms_infermedica(user_input, age, sex)
                if not symptoms:
                    return jsonify({"message": "Couldn’t identify symptoms. Please describe them differently.", 
                                   "follow_up": "", 
                                   "error_message": "Please provide more specific symptoms or check your input.",
                                   "user_input": user_input})

                user_session["evidence"].extend(symptoms)
                user_session["question_count"] = 0
                logger.debug(f"Appended initial evidence: {symptoms}")
                self.session_manager._save_sessions()  # Save after updating evidence

            # Step 2: Process User Answers to Follow-Up Questions
            if answer or free_text:
                if not user_session.get("last_question"):
                    return jsonify({"message": "No previous question to answer. Please provide symptoms first.", "follow_up": "", "user_input": user_input})

                if free_text:
                    if user_session["last_question"] and any("long" in q["name"].lower() or "duration" in q["name"].lower() for q in user_session["last_question"]):
                        parsed_evidence = self.nlp_processor.parse_duration_answer(free_text, user_session["last_question"][0]["name"], user_session["last_question"])
                    else:
                        parsed_evidence = self.nlp_processor.parse_free_text_answer(free_text, user_session["last_question"], user_session["last_question"][0]["name"])
                    
                    if not parsed_evidence:
                        return jsonify({"message": "Couldn’t understand your description. Please try again or select from the options.", 
                                       "follow_up": "", 
                                       "user_input": free_text})
                    user_session["evidence"].extend(parsed_evidence)
                    logger.debug(f"Appended free-text evidence: {parsed_evidence}")
                    self.session_manager._save_sessions()  # Save after updating evidence
                else:
                    if isinstance(answer, list):
                        if not answer:
                            return jsonify({"message": "No answer provided. Please select an option.", "follow_up": "", "user_input": user_input})
                        answer_value = answer[0]
                    else:
                        answer_value = answer

                    logger.debug(f"Processing answer: {answer_value}")

                    choice_id = {"yes": "present", "no": "absent", "don't know": "unknown"}.get(answer_value.lower(), "unknown")
                    if choice_id == "unknown" and user_session["last_question"]:
                        item_names = [item["name"].lower() for item in user_session["last_question"]]
                        match = process.extractOne(answer_value.lower(), item_names, score_cutoff=80)
                        if match:
                            selected_item = next(item for item in user_session["last_question"] if item["name"].lower() == match[0])
                            user_session["evidence"].append({"id": selected_item["id"], "choice_id": "present"})
                        else:
                            return jsonify({"message": "Couldn’t understand your answer. Please select from the options or describe your symptom.", 
                                           "follow_up": "", 
                                           "user_input": answer_value})
                    else:
                        user_session["evidence"].append({"id": user_session["last_question"][0]["id"], "choice_id": choice_id})
                    
                    user_session["question_count"] = user_session.get("question_count", 0) + 1
                    logger.debug(f"Updated evidence: {user_session['evidence'][-1]}, question_count: {user_session['question_count']}")
                    self.session_manager._save_sessions()  # Save after updating evidence and question count

            # Step 3: Get Diagnosis
            # Incorporate manual health data into evidence
            manual_health_data = user_session.get('manual_health_data', {})
            if 'temperature' in manual_health_data:
                temperature = manual_health_data['temperature']
                if temperature >= 38.0:  # Fever threshold
                    user_session["evidence"].append({"id": "s_98", "choice_id": "present"})  # Fever
                    self.session_manager._save_sessions()  # Save after updating evidence
            if 'blood_pressure' in manual_health_data:
                bp = manual_health_data['blood_pressure']
                systolic = bp['systolic']
                diastolic = bp['diastolic']
                if systolic >= 140 or diastolic >= 90:  # Hypertension threshold
                    user_session["evidence"].append({"id": "s_99", "choice_id": "present"})  # High blood pressure
                    self.session_manager._save_sessions()  # Save after updating evidence

            diagnosis = self.infermedica_client.get_diagnosis(
                evidence=user_session["evidence"],
                age=age,
                sex=sex,
                interview_id=user_session["interview_id"]
            )
            if "error" in diagnosis:
                logger.error(f"Diagnosis error payload: {json.dumps({'evidence': user_session['evidence'], 'interview_id': user_session['interview_id']})}")
                return jsonify({"message": f"Diagnosis error: {diagnosis['error']}. Please try again or contact support.", 
                               "follow_up": "", 
                               "error_message": "Diagnosis failed. Please try again or contact support.",
                               "user_input": user_input if user_input else answer})

            # Step 4: Determine Stopping Condition
            conditions = diagnosis.get("conditions", [])
            top_condition = max(conditions, key=lambda c: c["probability"]) if conditions else {"name": "Unknown", "probability": 0}
            should_stop = (
                user_session.get("question_count", 0) >= ChatConfig.MIN_QUESTIONS and 
                top_condition["probability"] >= ChatConfig.PROBABILITY_THRESHOLD
            ) or user_session.get("question_count", 0) >= ChatConfig.MAX_QUESTIONS or diagnosis.get("should_stop", False)

            logger.debug(f"Diagnosis conditions: {conditions}, top_condition: {top_condition}, should_stop: {should_stop}, question_count: {user_session.get('question_count', 0)}")

            # Step 5: Get Triage if Stopping
            triage_data = self.infermedica_client.get_triage(user_session["evidence"], age=age, sex=sex) if should_stop else {"triage_level": "unknown", "message": "We are still assessing your condition."}

            # Step 6: Handle Follow-Up Questions
            if "question" in diagnosis and diagnosis["question"].get("items") and not should_stop:
                user_session["last_question"] = diagnosis["question"]["items"]
                question_type = diagnosis["question"]["type"]
                question_text = diagnosis["question"]["text"]
                items = diagnosis["question"]["items"]

                is_binary_question = self.infermedica_client.is_yes_no_question(question_text)
                if is_binary_question:
                    options = ["Yes", "No", "Don't know"]
                    ui_hint = "dropdown"
                elif question_type in ["single", "group_single"]:
                    options = [item["name"] for item in items]
                    ui_hint = "dropdown"
                elif question_type == "group_multiple":
                    options = [item["name"] for item in items]
                    ui_hint = "checkboxes"
                else:
                    options = []
                    ui_hint = "text"

                follow_up = {
                    "text": question_text,
                    "type": question_type,
                    "options": options,
                    "ui_hint": ui_hint,
                    "is_binary": is_binary_question
                }
                logger.debug(f"Follow-up question: {follow_up}")
                self.session_manager._save_sessions()  # Save after setting last_question
            else:
                user_session["last_question"] = None
                follow_up = "This is my final assessment based on your symptoms."
                self.session_manager.reset_session(user_id)
                logger.debug(f"Triaging complete, resetting session for user_id: {user_id}")

            # Step 7: Format the Response
            response_text = self.infermedica_client.format_response(conditions, triage_data, is_final=should_stop)

            # Step 8: Integrate Fitbit Data (only for Fitbit users)
            smartwatch_data = None
            if 'fitbit_user' in session and session.get('access_token'):
                self.fitbit_client.set_access_token(session.get('access_token'))
                self.fitbit_client.set_refresh_token(session.get('refresh_token'))
                smartwatch_data = self.fitbit_client.get_basic_fitbit_data()
            else:
                smartwatch_data = {
                    "sp02": "N/A",
                    "heart_rate": "N/A"
                }

            logger.debug(f"Returning response: message={response_text}, follow_up={follow_up}, smartwatch_data={smartwatch_data}")

            return jsonify({
                "message": response_text,
                "follow_up": follow_up,
                "smartwatch_data": smartwatch_data,
                "error_message": "An unexpected error occurred." if "error" in diagnosis else None,
                "user_input": user_input if user_input else (answer if answer else free_text)
            })
        except Exception as e:
            logger.error(f"Error in chat_post: {str(e)}", exc_info=True)
            return jsonify({
                "message": "An unexpected error occurred. Please try again.",
                "follow_up": "",
                "error_message": str(e),
                "user_input": user_input if 'user_input' in locals() else (answer if 'answer' in locals() else free_text if 'free_text' in locals() else "")
            }), 500
        
    def reset(self):
        try:
            data = request.get_json()
            user_id = data.get('user_id', 'default')
            self.session_manager.reset_session(user_id)
            return jsonify({"message": "Session reset successfully. Start a new diagnosis by entering your symptoms.", "user_input": None})
        except Exception as e:
            logger.error(f"Error in reset: {str(e)}", exc_info=True)
            return jsonify({"message": "Error resetting session.", "error_message": str(e)}), 500

    def get_symptoms(self):
        try:
            with open(ChatConfig.CACHE_FILE, 'r') as f:
                symptoms = json.load(f)
            return jsonify({"symptoms": [symptom[0] for symptom in symptoms]})
        except FileNotFoundError:
            return jsonify({"symptoms": []}), 404
        except Exception as e:
            logger.error(f"Error in get_symptoms: {str(e)}", exc_info=True)
            return jsonify({"error": "Failed to retrieve symptoms."}), 500

    def feedback(self):
        try:
            data = request.get_json()
            user_id = data.get('user_id', 'default')
            feedback_response = data.get('feedback')
            if not user_id or not feedback_response:
                return jsonify({"message": "User ID and feedback are required"}), 400

            logger.info(f"Feedback from user {user_id}: {feedback_response}")
            return jsonify({"message": "Thank you for your feedback!"})
        except Exception as e:
            logger.error(f"Error in feedback: {str(e)}", exc_info=True)
            return jsonify({"message": "Error submitting feedback.", "error_message": str(e)}), 500

    def debug_token(self):
        try:
            logger.debug(f"Current session contents: {dict(session)}")
            if 'access_token' in session:
                return jsonify({"access_token": session['access_token']})
            return jsonify({"error": "No access token found"}), 400
        except Exception as e:
            logger.error(f"Error in debug_token: {str(e)}", exc_info=True)
            return jsonify({"error": "Failed to retrieve token."}), 500