import os
from openai import OpenAI
from dotenv import load_dotenv

# Load API key from the .env file
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

# Debugging step (REMOVE THIS AFTER CHECKING)
print(f"Loaded API Key: {api_key[:5]}...{api_key[-5:]}")  # Show only part of the key for verification

# Ensure key is available
if not api_key:
    raise ValueError("API Key not found. Ensure you have set OPENAI_API_KEY in your .env file.")


def chatbot_response(user_input):
    """ Function to get a chatbot response from GPT-4 """
    response = client.chat.completions.create(
        model="gpt-4o",  # Use GPT-4 or GPT-4o for better responses
        messages=[
            {"role": "system", "content": "You are a medical chatbot that helps with symptom analysis."},
            {"role": "user", "content": user_input}
        ]
    )
    return response.choices[0].message.content  # Extract response text

# Run chatbot in CLI
if __name__ == "__main__":
    print("AI Healthcare Chatbot (Type 'exit' to quit)")
    while True:
        user_query = input("You: ")
        if user_query.lower() in ["exit", "quit"]:
            print("Chatbot: Goodbye!")
            break
        response = chatbot_response(user_query)
        print("Chatbot:", response)