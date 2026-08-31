import os, psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from dotenv import load_dotenv
load_dotenv()

CFG = dict(host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT", "5432"),
           dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
           password=os.getenv("DB_PASSWORD"), sslmode="require")

@contextmanager
def cursor(commit=False):
    conn = psycopg2.connect(**CFG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        yield cur
        if commit: conn.commit()
    finally:
        cur.close(); conn.close()

def init_db():
    with cursor(commit=True) as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE, email VARCHAR(255) UNIQUE,
            password_hash VARCHAR(255), is_verified BOOLEAN DEFAULT FALSE,
            role VARCHAR(20) NOT NULL DEFAULT 'employee')""")
        cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'employee'""")
        cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0""")
        cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP""")
        cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Kolkata')""")
        cur.execute("""ALTER TABLE users ALTER COLUMN created_at SET DEFAULT (NOW() AT TIME ZONE 'Asia/Kolkata')""")
        cur.execute("""CREATE TABLE IF NOT EXISTS otp_codes (
            id SERIAL PRIMARY KEY, email VARCHAR(255), code VARCHAR(6),
            purpose VARCHAR(20), expires_at TIMESTAMP, used BOOLEAN DEFAULT FALSE)""")

        cur.execute("""CREATE TABLE IF NOT EXISTS mood_logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            mood_date DATE NOT NULL DEFAULT ((NOW() AT TIME ZONE 'Asia/Kolkata')::date),
            sentiment VARCHAR(20),
            emotion VARCHAR(30),
            compound_score REAL,
            confidence REAL,
            journal_text TEXT,
            source VARCHAR(10) NOT NULL DEFAULT 'manual',
            created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Kolkata'))""")
        cur.execute("""ALTER TABLE mood_logs ADD COLUMN IF NOT EXISTS source VARCHAR(10) NOT NULL DEFAULT 'manual'""")
        cur.execute("""ALTER TABLE mood_logs ADD COLUMN IF NOT EXISTS confidence REAL""")
        cur.execute("""ALTER TABLE mood_logs ALTER COLUMN mood_date SET DEFAULT ((NOW() AT TIME ZONE 'Asia/Kolkata')::date)""")
        cur.execute("""ALTER TABLE mood_logs ALTER COLUMN created_at SET DEFAULT (NOW() AT TIME ZONE 'Asia/Kolkata')""")
        cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_photo BYTEA""")
        cur.execute("""CREATE INDEX IF NOT EXISTS idx_mood_logs_user_date
            ON mood_logs(user_id, mood_date)""")

        cur.execute("""CREATE TABLE IF NOT EXISTS questionnaire_responses (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            submitted_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Kolkata'),
            answers JSONB NOT NULL,
            total_score INTEGER NOT NULL,
            max_score INTEGER NOT NULL,
            category VARCHAR(30) NOT NULL,
            wants_to_talk VARCHAR(10))""")
        cur.execute("""ALTER TABLE questionnaire_responses ALTER COLUMN submitted_at SET DEFAULT (NOW() AT TIME ZONE 'Asia/Kolkata')""")
        cur.execute("""CREATE INDEX IF NOT EXISTS idx_questionnaire_user_date
            ON questionnaire_responses(user_id, submitted_at)""")

MOOD_LABELS = ["Happy", "Neutral", "Sad", "Stress", "Angry", "Fear"]

MOOD_EMOJI = {
    "Happy": "\U0001F60A",
    "Neutral": "\U0001F610",
    "Sad": "\U0001F622",
    "Stress": "\U0001F62B",
    "Angry": "\U0001F620",
    "Fear": "\U0001F628",
}

def save_manual_mood(user_id, mood_label):
    with cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO mood_logs (user_id, sentiment, source)
               VALUES (%s, %s, 'manual')""",
            (user_id, mood_label),
        )

def save_profile_photo(user_id, photo_bytes):
    with cursor(commit=True) as cur:
        cur.execute(
            "UPDATE users SET profile_photo=%s WHERE id=%s",
            (psycopg2.Binary(photo_bytes), user_id),
        )

def get_profile_photo(user_id):
    with cursor() as cur:
        cur.execute("SELECT profile_photo FROM users WHERE id=%s", (user_id,))
        row = cur.fetchone()
        if row and row["profile_photo"] is not None:
            return bytes(row["profile_photo"])
        return None

def save_mood_log(user_id, sentiment, emotion, compound_score, journal_text, confidence=None):
    mood_label = emotion if emotion in MOOD_LABELS else "Neutral"
    with cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO mood_logs (user_id, sentiment, emotion, compound_score, confidence, journal_text, source)
               VALUES (%s, %s, %s, %s, %s, %s, 'nlp')""",
            (user_id, mood_label, emotion, compound_score, confidence, journal_text),
        )

def get_mood_logs_for_month(user_id, year, month):
    with cursor() as cur:
        cur.execute(
            """SELECT DISTINCT ON (mood_date) mood_date, sentiment, emotion, compound_score, confidence, created_at
               FROM mood_logs
               WHERE user_id = %s
                 AND EXTRACT(YEAR FROM mood_date) = %s
                 AND EXTRACT(MONTH FROM mood_date) = %s
               ORDER BY mood_date, created_at DESC""",
            (user_id, year, month),
        )
        return cur.fetchall()

def get_user_mood_history(user_id, limit=200):
    with cursor() as cur:
        cur.execute(
            """SELECT mood_date, sentiment, emotion, compound_score, confidence, journal_text, source, created_at
               FROM mood_logs
               WHERE user_id = %s
               ORDER BY created_at DESC
               LIMIT %s""",
            (user_id, limit),
        )
        return cur.fetchall()

def get_all_employee_mood_logs(limit_days=30):
    with cursor() as cur:
        cur.execute(
            """SELECT u.username, u.email, m.mood_date, m.sentiment, m.emotion, m.compound_score, m.confidence, m.created_at
               FROM mood_logs m
               JOIN users u ON u.id = m.user_id
               WHERE u.role = 'employee'
                 AND m.mood_date >= ((NOW() AT TIME ZONE 'Asia/Kolkata')::date) - (%s || ' days')::interval
               ORDER BY m.mood_date DESC, u.username""",
            (limit_days,),
        )
        return cur.fetchall()

def get_latest_mood_per_employee():
    with cursor() as cur:
        cur.execute(
            """SELECT DISTINCT ON (u.id) u.username, u.email, m.mood_date, m.sentiment, m.emotion, m.confidence, m.created_at
               FROM users u
               JOIN mood_logs m ON m.user_id = u.id
               WHERE u.role = 'employee'
               ORDER BY u.id, m.created_at DESC"""
        )
        return cur.fetchall()

QUESTIONNAIRE_QUESTIONS = [
    {"id": "q1_current_mood", "text": "How are you feeling right now?", "scored": False,
     "options": ["Very Happy", "Happy", "Neutral", "Sad", "Angry", "Anxious/Fearful"]},

    {"id": "q2_overall_mood", "text": "How would you rate your overall mood today?", "scored": True, "reverse": False,
     "options": ["1 - Very Poor", "2 - Poor", "3 - Average", "4 - Good", "5 - Excellent"]},

    {"id": "q3_stress", "text": "How stressed do you feel right now?", "scored": True, "reverse": True,
     "options": ["Not stressed", "Slightly stressed", "Moderately stressed", "Highly stressed", "Extremely stressed"]},

    {"id": "q4_main_factor", "text": "What is the main thing affecting your mood today?", "scored": False,
     "options": ["Work", "Relationships", "Financial concerns", "Health", "Family",
                 "Sleep/Fatigue", "Personal concerns", "Nothing specific", "Other"]},

    {"id": "q5_energy", "text": "How would you describe your energy level today?", "scored": True, "reverse": False,
     "options": ["Very Low", "Low", "Moderate", "High", "Very High"]},

    {"id": "q6_sleep", "text": "How well did you sleep recently?", "scored": True, "reverse": False,
     "options": ["Very Poor", "Poor", "Average", "Good", "Very Good"]},

    {"id": "q7_support_pref", "text": "What kind of support would you prefer right now?", "scored": False,
     "options": ["Breathing/Relaxation Exercise", "Journaling Prompt", "Motivational Content",
                 "Cognitive Reframing", "Mindfulness Activity", "Professional Support Information"]},

    {"id": "q8_want_to_talk", "text": "Would you like to talk about what is bothering you?", "scored": False,
     "options": ["Yes", "Maybe", "No"]},

    {"id": "q9_negative_freq", "text": "How often have you been experiencing negative emotions recently?",
     "scored": True, "reverse": True,
     "options": ["Never", "Rarely", "Sometimes", "Often", "Very Often"]},

    {"id": "q10_confidence", "text": "How confident are you in managing your emotions today?",
     "scored": True, "reverse": False,
     "options": ["Not confident", "Slightly confident", "Moderately confident", "Very confident", "Extremely confident"]},

    {"id": "q11_help_now", "text": "What would help you feel better right now?", "scored": False,
     "options": ["Relaxation", "Someone to talk to", "Motivation", "Taking a break",
                 "Organizing my tasks", "Physical activity", "Sleep/rest", "I'm not sure"]},

    {"id": "q12_personalize", "text": "Would you like MoodMentor to personalize future recommendations based on your answers?",
     "scored": False, "options": ["Yes", "No"]},
]

_SCORED_QUESTIONS = [q for q in QUESTIONNAIRE_QUESTIONS if q["scored"]]
QUESTIONNAIRE_MAX_SCORE = len(_SCORED_QUESTIONS) * 5
QUESTIONNAIRE_MIN_SCORE = len(_SCORED_QUESTIONS) * 1

def score_questionnaire(answers: dict) -> dict:
    total = 0
    for q in _SCORED_QUESTIONS:
        value = q["options"].index(answers[q["id"]]) + 1  
        total += (6 - value) if q["reverse"] else value

    if total >= 24:
        category = "Thriving"
    elif total >= 18:
        category = "Doing Well"
    elif total >= 12:
        category = "Needs Attention"
    else:
        category = "At Risk"

    return {"total_score": total, "max_score": QUESTIONNAIRE_MAX_SCORE, "category": category}

def save_questionnaire_response(user_id, answers: dict, total_score: int, category: str):
    import json as _json
    wants_to_talk = answers.get("q8_want_to_talk")
    with cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO questionnaire_responses (user_id, answers, total_score, max_score, category, wants_to_talk)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (user_id, _json.dumps(answers), total_score, QUESTIONNAIRE_MAX_SCORE, category, wants_to_talk),
        )

def get_questionnaire_history(user_id, limit=100):
    with cursor() as cur:
        cur.execute(
            """SELECT submitted_at, answers, total_score, max_score, category, wants_to_talk
               FROM questionnaire_responses
               WHERE user_id = %s
               ORDER BY submitted_at DESC
               LIMIT %s""",
            (user_id, limit),
        )
        return cur.fetchall()

def get_all_questionnaire_responses(limit_days=30):
    with cursor() as cur:
        cur.execute(
            """SELECT u.username, u.email, q.submitted_at, q.answers,
                      q.total_score, q.max_score, q.category, q.wants_to_talk
               FROM questionnaire_responses q
               JOIN users u ON u.id = q.user_id
               WHERE u.role = 'employee'
                 AND q.submitted_at >= ((NOW() AT TIME ZONE 'Asia/Kolkata')::date) - (%s || ' days')::interval
               ORDER BY q.submitted_at DESC, u.username""",
            (limit_days,),
        )
        return cur.fetchall()
