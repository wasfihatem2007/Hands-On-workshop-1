import os
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "super_secret_med_key"

MODEL_NAME = "gemini-flash-latest"

SENDER_EMAIL = os.environ.get("MAIL_USERNAME")
SENDER_PASSWORD = os.environ.get("MAIL_PASSWORD")
MODERATOR_EMAIL = os.environ.get("MODERATOR_EMAIL")

TRAINING_GUIDELINES = """
*** CRITICAL SIMULATION RULES ***
1. NON-DISCLOSURE: NEVER confirm a medical diagnosis. If the student asks "Do you have appendicitis?" or guesses the disease, YOU MUST SAY: "I'm not sure what it is, I just know how I feel." or "That's for you to tell me, doctor."
2. PACING (STACKING QUESTIONS): If the student asks two or more distinct questions in one message (e.g., "Do you smoke? AND How old are you?"), ACT CONFUSED. Say something like "You're asking too fast..." or "One thing at a time, please." ONLY answer the very first question they asked. Ignore the rest.
3. RAPPORT CHECK: 
   - Start the conversation slightly guarded/cold.
   - If the student DOES NOT introduce themselves or asks for your name too late, remain cold and give short answers.
   - If the student uses empathetic statements (e.g., "I'm sorry to hear that"), become "talkative" and open up more.
"""

PERSONAS = {
    "1": {
        "name": "Patient 1: Ahmed (Respiratory)",
        "key_env_var": "PATIENT_1_KEY",
        "instruction": f"""
        You are Ahmed, a 59-year-old male construction worker. 
        CHIEF COMPLAINT: Chronic cough and shortness of breath.
        HISTORY: You have smoked 1 pack a day for 40 years. You get winded climbing stairs. 
        PERSONALITY: You are stubborn, slightly dismissive of doctors, and hate being told to quit smoking. 
        GOAL: The student needs to ask about your smoking history, occupation, and family history.
        {TRAINING_GUIDELINES}
        """
    },
    "2": {
        "name": "Patient 2: Sarah (Gastrointestinal)",
        "key_env_var": "PATIENT_2_KEY",
        "instruction": f"""
        You are Sarah, a 24-year-old medical student (ironically).
        CHIEF COMPLAINT: Sharp pain in the lower right abdomen.
        HISTORY: Pain started near the belly button yesterday and moved down. You have nausea but no vomiting.
        PERSONALITY: You are anxious and worried it might be appendicitis because you have exams next week.
        GOAL: The student needs to ask about pain migration, fever, and last meal.
        {TRAINING_GUIDELINES}
        """
    },
    "3": {
        "name": "Patient 3: Mr. Thompson (Cardio/Geriatric)",
        "key_env_var": "PATIENT_3_KEY",
        "instruction": f"""
        You are Mr. Thompson, a 78-year-old retired teacher.
        CHIEF COMPLAINT: "I had a little dizzy spell."
        HISTORY: You fainted while gardening this morning. You take medication for high blood pressure but forgot it for the last 3 days.
        PERSONALITY: You are very polite, talkative, and tend to go off-topic about your garden.
        GOAL: The student must identify the medication non-adherence and rule out a stroke.
        {TRAINING_GUIDELINES}
        """
    }
}

chat_histories = {}

def send_email_log(patient_name, log_content):
    """Sends the session log to the moderator via email."""
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("Email credentials missing. Log not sent.")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = MODERATOR_EMAIL
        msg['Subject'] = f"Hands On Log - {patient_name} - {datetime.datetime.now().strftime('%H:%M')}"

        msg.attach(MIMEText(log_content, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, MODERATOR_EMAIL, text)
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

@app.route('/')
def index():
    return render_template('index.html', personas=PERSONAS)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get('message')
    patient_id = data.get('patient_id')
    selected_language = data.get('language', 'English') # Default to English
    
    user_session_id = session.get('session_id', str(os.urandom(16).hex()))
    session['session_id'] = user_session_id
    
    if patient_id not in PERSONAS:
        return jsonify({"error": "Invalid Patient ID"}), 400
    env_var_name = PERSONAS[patient_id]['key_env_var']
    specific_api_key = os.getenv(env_var_name)
    if not specific_api_key:
        return jsonify({"error": f"API Key for Patient {patient_id} not found on server."}), 500

    genai.configure(api_key=specific_api_key)

    key = f"{user_session_id}_{patient_id}"
    if key not in chat_histories:
        chat_histories[key] = [
            {"role": "user", "parts": [PERSONAS[patient_id]['instruction']]},
            {"role": "model", "parts": ["(Internal: Ready.)"]}
        ]
        session[f'lang_{key}'] = 'English'

    last_lang = session.get(f'lang_{key}', 'English')
    if selected_language != last_lang:
        switch_instruction = f"(System Command: The user has switched the language to {selected_language}. Please respond in {selected_language} from now on, but keep your persona character.)"
        chat_histories[key].append({"role": "user", "parts": [switch_instruction]})
        chat_histories[key].append({"role": "model", "parts": [f"(Understood. Switching to {selected_language}.)"]})
        session[f'lang_{key}'] = selected_language

    history = chat_histories[key]
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        chat_session = model.start_chat(history=history)
        response = chat_session.send_message(user_msg)
        
        ai_text = response.text
        
        chat_histories[key].append({"role": "user", "parts": [user_msg]})
        chat_histories[key].append({"role": "model", "parts": [ai_text]})
        
        return jsonify({"response": ai_text})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/reset', methods=['POST'])
def reset():
    data = request.json
    patient_id = data.get('patient_id')
    user_session_id = session.get('session_id')
    key = f"{user_session_id}_{patient_id}"
    
    if key in chat_histories:
        history = chat_histories[key]
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        patient_name = PERSONAS[patient_id]['name']
        
        log_content = f"SESSION LOG - HANDS ON PROJECT\n"
        log_content += f"Patient: {patient_name}\n"
        log_content += f"Time: {timestamp}\n"
        log_content += "-" * 30 + "\n"
        
        for entry in history:
            role = "Student" if entry['role'] == "user" else "Patient AI"
            text = entry['parts'][0]
            if "You are" in text or "TRAINING_GUIDELINES" in text or "System Command" in text: continue 
            log_content += f"{role}: {text}\n"
        
        send_email_log(patient_name, log_content)
        
        del chat_histories[key]
        return jsonify({"status": "success", "message": "Session reset and log sent to moderator."})
    
    return jsonify({"status": "error", "message": "No active session found."})

if __name__ == '__main__':
    app.run(debug=True)