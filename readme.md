Below is a detailed `README.md` file for your HealthSync AI Chatbot project. This README is designed to provide comprehensive documentation without including any sensitive information (e.g., API keys, credentials, or other triggers for GitHub’s push protection). It includes setup instructions, project structure, usage details, deployment information, and future improvements, all tailored to your project based on the work we’ve done.

---

# HealthSync AI Chatbot

HealthSync AI Chatbot is a web application that provides health insights and symptom-based triaging using the Infermedica API and Fitbit data. Users can log in with Fitbit or Auth0, input symptoms, and receive potential diagnoses and health recommendations. The app also allows users to manually input health data (e.g., temperature, blood pressure) to enhance diagnostic accuracy.

## Features
- **Fitbit Integration:** Log in with Fitbit to access SpO2 and heart rate data, with insights generated using OpenAI.
- **Auth0 Authentication:** Alternative login for non-Fitbit users, supporting secure authentication.
- **Symptom Triage:** Uses the Infermedica API to analyze symptoms and provide potential diagnoses and triage recommendations.
- **Manual Health Data Input:** Add temperature and blood pressure to improve diagnostic accuracy.
- **Health Dashboard:** View Fitbit data and manually entered health metrics in a centralized dashboard.
- **Profile & Settings:** View user information and manage settings.
- **Responsive Design:** Clean, aligned UI with a modern color scheme, optimized for desktop and mobile devices.
- **Navigation System:** Three-dot menu for easy access to Fitbit Info, Profile & Settings, Health Dashboard, and Sign Out.

## Prerequisites
To run this project locally, you’ll need the following:

- **Python 3.11+**
- **Fitbit Developer Account:** For API credentials to enable Fitbit login and data access.
- **Auth0 Account:** For authentication credentials to enable Auth0 login.
- **OpenAI API Key:** For generating health insights based on Fitbit data.
- **Infermedica API Credentials:** For symptom triaging and diagnosis.

## Setup Instructions

### 1. Clone the Repository
Clone the repository to your local machine:

```bash
git clone https://github.com/danielmorodolu/healthsync-AI-Chatbot.git
cd healthsync-AI-Chatbot
```

### 2. Create a Virtual Environment
Set up a virtual environment to manage dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
Install the required Python packages listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables
Create a `.env` file in the project root and add the following environment variables. Replace the placeholders with your actual credentials:

```plaintext
FLASK_SECRET_KEY=your-flask-secret-key
FITBIT_CLIENT_ID=your-fitbit-client-id
FITBIT_CLIENT_SECRET=your-fitbit-client-secret
AUTH0_DOMAIN=your-auth0-domain
AUTH0_CLIENT_ID=your-auth0-client-id
AUTH0_CLIENT_SECRET=your-auth0-client-secret
AUTH0_CALLBACK_URL=http://127.0.0.1:5000/auth0/callback
OPENAI_API_KEY=your-openai-api-key
INFERMEDICA_APP_ID=your-infermedica-app-id
INFERMEDICA_APP_KEY=your-infermedica-app-key
```

- **FLASK_SECRET_KEY:** A random string for Flask session security.
- **FITBIT_CLIENT_ID/SECRET:** Obtain from the Fitbit Developer Portal.
- **AUTH0_DOMAIN/ID/SECRET:** Obtain from the Auth0 Dashboard.
- **AUTH0_CALLBACK_URL:** Set to `http://127.0.0.1:5000/auth0/callback` for local development.
- **OPENAI_API_KEY:** Obtain from the OpenAI Dashboard.
- **INFERMEDICA_APP_ID/KEY:** Obtain from the Infermedica Developer Portal.

### 5. Run the Application Locally
Start the Flask development server:

```bash
python app.py
```

The app will be available at `http://127.0.0.1:5000`.

## Project Structure
The project is organized as follows:

```
healthsync-AI-Chatbot/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── README.md               # Project documentation
├── chatbot/                # Chatbot-related modules
│   ├── routes.py           # Chat routes and triaging logic
│   ├── session_manager.py  # Session management for user data
│   ├── infermedica.py      # Infermedica API integration
│   ├── nlp.py              # NLP processing for symptom parsing
│   └── config.py           # Configuration settings
├── fitbit/                 # Fitbit integration
│   └── fitbit.py           # Fitbit API client
├── auth/                   # Authentication logic
│   └── auth.py             # Fitbit and Auth0 authentication
├── utils/                  # Utility functions
│   └── helpers.py          # Helper functions (e.g., symptom caching)
├── static/                 # Static assets
│   ├── css/
│   │   └── style.css       # CSS styles for the UI
│   ├── js/
│   │   └── script.js       # JavaScript for client-side functionality
│   └── images/
│       └── healthsync-logo.png  # Logo image
└── templates/              # HTML templates
    ├── chat.html           # Main chat interface
    ├── edit_profile.html   # Edit age and gender
    ├── fitbit_info.html    # Fitbit data and insights
    ├── health_data.html    # Manual health data input
    ├── health_dashboard.html  # Health data dashboard
    ├── index.html          # Login page
    └── profile.html        # Profile and settings page
```

## Usage
1. **Access the App:** Open `http://127.0.0.1:5000` in your browser.
2. **Log In:** Choose to log in with Fitbit or Auth0.
3. **Enter Age and Gender:** On the chat page, enter your age and gender (required for triaging).
4. **Input Symptoms:** Type symptoms (e.g., "I have a headache") to start the triaging process.
5. **Add Health Data:** Optionally, add manual health data (temperature, blood pressure) to enhance diagnoses.
6. **Navigate:** Use the three-dot menu to access Fitbit Info, Profile & Settings, Health Dashboard, or Sign Out.

## Deployment
The app is deployed on Render and can be accessed at: [https://healthsync-ai-chatbot.onrender.com](https://healthsync-ai-chatbot.onrender.com)

### Deployment Steps (Render)
1. **Push to GitHub:** Ensure your code is in a public GitHub repository.
2. **Create a Web Service on Render:**
   - Go to [Render](https://render.com) and create a new web service.
   - Connect your GitHub repository (`healthsync-AI-Chatbot`).
   - Configure the service:
     - **Environment:** Python 3
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `gunicorn --bind 0.0.0.0:$PORT app:app`
     - **Instance Type:** Free
   - Add environment variables (same as in your `.env` file).
3. **Deploy:** Render will build and deploy your app, providing a URL upon completion.

## Future Improvements
- **Responsive Design with Tailwind CSS:** Enhance the UI with Tailwind CSS for better responsiveness across devices.
- **Accessibility Improvements:** Add ARIA labels, keyboard navigation, and screen reader support.
- **Health Insights Dashboard:** Create a dashboard with charts to visualize health data trends (e.g., using Chart.js).
- **Database Integration:** Replace session-based storage with a database (e.g., PostgreSQL) for persistent user data.
- **Enhanced NLP:** Improve symptom parsing with more advanced NLP techniques.

## Troubleshooting
- **Fitbit Login Fails:** Ensure your Fitbit API credentials are correct and the callback URL matches your app’s URL.
- **Auth0 Login Fails:** Verify your Auth0 credentials and callback URL in the Auth0 Dashboard.
- **Triaging Errors:** Check your Infermedica API credentials and ensure the API is accessible.
- **Deployment Issues:** Review Render’s logs for errors and ensure all environment variables are set correctly.

## License
This project is licensed under the MIT License.

---

### Notes on GitHub Push Protection
- **No Sensitive Data:** The README avoids including any sensitive information (e.g., API keys, credentials) that could trigger GitHub’s push protection. All references to environment variables are placeholders (e.g., `your-openai-api-key`).
- **Environment Variables:** Instructions for setting environment variables are provided without exposing actual values.
- **Deployment Instructions:** The deployment section includes the Render URL but no sensitive configuration details.

### Next Steps
- **Test the Deployed App:** Ensure all features (login, triaging, navigation) work as expected on the deployed URL (`https://healthsync-ai-chatbot.onrender.com`).
