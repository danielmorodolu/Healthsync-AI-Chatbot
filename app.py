import logging
from flask import Flask, render_template, session, redirect, url_for, request, jsonify
from decouple import config
from chatbot.routes import ChatRoutes
from fitbit.fitbit import FitbitClient
from chatbot.session_manager import SessionManager
from chatbot.infermedica import InfermedicaClient
from chatbot.nlp import NLPProcessor
from utils.helpers import load_cached_symptoms
from auth.auth import AuthManager
from openai import OpenAI
import httpx

app = Flask(__name__)
app.secret_key = config("FLASK_SECRET_KEY")
app.config['SESSION_TYPE'] = 'filesystem'

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load cached symptoms
symptom_map = load_cached_symptoms()

# Initialize components
session_manager = SessionManager()
infermedica_client = InfermedicaClient()
nlp_processor = NLPProcessor()
nlp_processor.load_symptom_map(symptom_map)
fitbit_client = FitbitClient()

# Initialize OpenAI client
http_client = httpx.Client()
openai_client = OpenAI(api_key=config("OPENAI_API_KEY"), http_client=http_client)

# Setup authentication routes using AuthManager
auth_manager = AuthManager(app)

# Setup chat routes
chat_routes = ChatRoutes(app, session_manager, infermedica_client, nlp_processor, fitbit_client, symptom_map)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health_data', methods=['GET'])
def health_data_get():
    if 'auth0_user' not in session and 'fitbit_user' not in session:
        return redirect(url_for('index'))
    return render_template('health_data.html', user_id=session.get('user_id', 'default'))

@app.route('/health_data', methods=['POST'])
def health_data_post():
    data = request.get_json()
    user_id = data.get('user_id', 'default')
    temperature = data.get('temperature')
    blood_pressure_systolic = data.get('blood_pressure_systolic')
    blood_pressure_diastolic = data.get('blood_pressure_diastolic')

    # Store health data in session for use in diagnosis
    user_session = session_manager.get_session(user_id)
    if temperature:
        user_session['manual_health_data'] = user_session.get('manual_health_data', {})
        user_session['manual_health_data']['temperature'] = float(temperature)
    if blood_pressure_systolic and blood_pressure_diastolic:
        user_session['manual_health_data'] = user_session.get('manual_health_data', {})
        user_session['manual_health_data']['blood_pressure'] = {
            'systolic': int(blood_pressure_systolic),
            'diastolic': int(blood_pressure_diastolic)
        }

    return jsonify({"message": "Health data submitted successfully."})

@app.route('/edit_profile', methods=['GET'])
def edit_profile_get():
    if 'auth0_user' not in session and 'fitbit_user' not in session:
        return redirect(url_for('index'))

    user_id = session.get('user_id', 'default')
    user_session = session_manager.get_session(user_id)
    return render_template('edit_profile.html', user_id=user_id, age=user_session.get('age'), sex=user_session.get('sex'))

@app.route('/edit_profile', methods=['POST'])
def edit_profile_post():
    data = request.get_json()
    user_id = data.get('user_id', 'default')
    age = int(data.get('age', 30))
    sex = data.get('sex', 'male')

    # Update session with new age and sex
    user_session = session_manager.get_session(user_id)
    user_session['age'] = age
    user_session['sex'] = sex

    return jsonify({"message": "Profile updated successfully."})

@app.route('/fitbit_info')
def fitbit_info():
    if 'auth0_user' not in session and 'fitbit_user' not in session:
        return redirect(url_for('index'))

    smartwatch_data = None
    insights = None
    if 'fitbit_user' in session:
        fitbit_client.set_access_token(session.get('access_token'))
        smartwatch_data = fitbit_client.get_fitbit_data()
        if smartwatch_data and (smartwatch_data['sp02'] != 'N/A' or smartwatch_data['heart_rate'] != 'N/A'):
            prompt = f"Analyze the following Fitbit data and provide health insights and improvement tips: SpO2: {smartwatch_data['sp02']}%, Heart Rate: {smartwatch_data['heart_rate']} bpm."
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a health assistant providing insights based on Fitbit data."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200
            )
            insights = response.choices[0].message.content.strip()

    return render_template('fitbit_info.html', smartwatch_data=smartwatch_data, insights=insights)

@app.route('/profile')
def profile():
    if 'auth0_user' not in session and 'fitbit_user' not in session:
        return redirect(url_for('index'))

    user_info = session.get('auth0_user', session.get('fitbit_user', {}))
    return render_template('profile.html', user_info=user_info)

@app.route('/health_dashboard')
def health_dashboard():
    if 'auth0_user' not in session and 'fitbit_user' not in session:
        return redirect(url_for('index'))

    user_id = session.get('user_id', 'default')
    user_session = session_manager.get_session(user_id)
    manual_health_data = user_session.get('manual_health_data', {})

    smartwatch_data = None
    if 'fitbit_user' in session:
        fitbit_client.set_access_token(session.get('access_token'))
        smartwatch_data = fitbit_client.get_fitbit_data()

    return render_template('health_dashboard.html', smartwatch_data=smartwatch_data, manual_health_data=manual_health_data)


gunicorn --bind 0.0.0.0:$PORT app:app


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)