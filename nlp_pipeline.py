import os
import re
import ftfy
import emoji
import spacy
import torch
import stopwordsiso
from transformers import (
    pipeline as hf_pipeline,
)
from langdetect import detect, DetectorFactory
from deep_translator import GoogleTranslator
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from recommendations import get_recommendation, WELLNESS_RECOMMENDATIONS
from huggingface_hub import InferenceClient

# Restrict PyTorch CPU threads to 1 to avoid saturating shared container CPU quota
torch.set_num_threads(1)

# Streamlit-compatible resource cache decorator (falls back gracefully if run outside Streamlit)
try:
    import streamlit as st
    cache_resource = st.cache_resource
except Exception:
    def cache_resource(fn):
        return fn

DetectorFactory.seed = 0

PRIMARY_CHAT_MODELS = [
    "Qwen/Qwen2.5-72B-Instruct",
    "meta-llama/Llama-3.1-8B-Instruct",
    "deepseek-ai/DeepSeek-V3",
    "Qwen/Qwen2.5-Coder-32B-Instruct",
]
BERT_EMOTION_MODEL_NAME = "bhadresh-savani/bert-base-go-emotion"

LANGUAGE_NAMES = {
    "te": "Telugu", "kn": "Kannada", "en": "English", "ta": "Tamil",
    "hi": "Hindi", "ml": "Malayalam", "mr": "Marathi", "bn": "Bengali", "gu": "Gujarati",
    "fr": "French", "de": "German", "es": "Spanish", "pt": "Portuguese",
    "ar": "Arabic", "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "ru": "Russian",
}

def _get_stopwords(language_code: str) -> set:
    if stopwordsiso.has_lang(language_code):
        return stopwordsiso.stopwords(language_code)
    return set()

EMOTION_LABELS = ["Happy", "Sad", "Stress", "Angry", "Fear", "Neutral"]

GOEMOTIONS_TO_APP_LABEL = {
    "joy": "Happy", "amusement": "Happy", "excitement": "Happy",
    "love": "Happy", "gratitude": "Happy", "optimism": "Happy",
    "relief": "Happy", "pride": "Happy", "admiration": "Happy",
    "approval": "Happy", "caring": "Happy",

    "sadness": "Sad", "disappointment": "Sad", "grief": "Sad",
    "remorse": "Sad",

    "nervousness": "Stress", "embarrassment": "Stress",
    "confusion": "Stress",

    "anger": "Angry", "annoyance": "Angry", "disgust": "Angry",
    "disapproval": "Angry",

    "fear": "Fear",

    "neutral": "Neutral", "realization": "Neutral", "surprise": "Neutral",
    "curiosity": "Neutral", "desire": "Neutral",
}

@cache_resource
def _get_nlp():
    """Fast, lightweight sentence tokenizer using spaCy blank model (~15MB RAM)."""
    nlp = spacy.blank("en")
    if "sentencizer" not in nlp.pipe_names:
        nlp.add_pipe("sentencizer")
    return nlp

@cache_resource
def _get_vader():
    return SentimentIntensityAnalyzer()

@cache_resource
def _get_bert_emotion_pipeline():
    """Load BERT emotion classifier with PyTorch dynamic 8-bit quantization to cut memory by ~50%."""
    pipe = hf_pipeline(
        "text-classification",
        model=BERT_EMOTION_MODEL_NAME,
        top_k=None,
        device=-1,
    )
    try:
        pipe.model = torch.quantization.quantize_dynamic(
            pipe.model, {torch.nn.Linear}, dtype=torch.qint8
        )
    except Exception as e:
        print(f"[BERT] Dynamic quantization skipped: {e}")
    return pipe

def _bert_emotion(text: str) -> dict:
    classifier = _get_bert_emotion_pipeline()

    if not text.strip():
        text = "(empty feedback)"

    raw_predictions = classifier(text, truncation=True)[0]

    app_scores = {label: 0.0 for label in EMOTION_LABELS}
    for pred in raw_predictions:
        goemotion_label = pred["label"].lower()
        app_label = GOEMOTIONS_TO_APP_LABEL.get(goemotion_label, "Neutral")
        app_scores[app_label] += pred["score"]

    total = sum(app_scores.values()) or 1.0
    app_scores = {label: round(score / total, 4) for label, score in app_scores.items()}

    final_emotion = max(app_scores, key=app_scores.get)
    confidence = app_scores[final_emotion]
    return {"emotion": final_emotion, "scores": app_scores, "confidence": confidence}

def classify_emotion(text: str) -> dict:
    return _bert_emotion(text)

def process_employee_feedback(text: str) -> dict:
    nlp = _get_nlp()
    vader = _get_vader()

    normalized_text = ftfy.fix_text(text)

    try:
        language = detect(normalized_text)
    except Exception:
        language = "unknown"
    detected_language = LANGUAGE_NAMES.get(language, "Other / Unknown")

    emoji_list = [ch for ch in normalized_text if ch in emoji.EMOJI_DATA]

    cleaned_text = re.sub(r"https?://\S+|www\.\S+", " ", normalized_text)
    cleaned_text = re.sub(r"\S+@\S+", " ", cleaned_text)
    cleaned_text = re.sub(r"@\w+|#\w+", " ", cleaned_text)
    cleaned_text = emoji.replace_emoji(cleaned_text, replace="")
    cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

    doc = nlp(cleaned_text)
    sentences = [s.text.strip() for s in doc.sents if s.text.strip()]
    original_tokens = [t.text for t in doc if not t.is_space]
    clean_tokens = [t.text for t in doc if not t.is_punct and not t.is_space and not t.like_num]

    selected_stopwords = _get_stopwords(language)
    filtered_tokens = [t for t in clean_tokens if t.lower() not in selected_stopwords]
    final_preprocessed_text = " ".join(filtered_tokens)

    if language and language not in ("en", "unknown") and final_preprocessed_text.strip():
        try:
            translated_text = GoogleTranslator(source="auto", target="en").translate(final_preprocessed_text)
        except Exception as error:
            translated_text = final_preprocessed_text
    else:
        translated_text = final_preprocessed_text

    english_doc = nlp(translated_text)
    lemmas = [t.lemma_ if hasattr(t, "lemma_") and t.lemma_ else t.text for t in english_doc if not t.is_space]
    lemmatized_text = " ".join(lemmas)

    sentiment_scores = vader.polarity_scores(translated_text)
    compound_score = sentiment_scores["compound"]
    if compound_score >= 0.05:
        final_sentiment = "Positive"
    elif compound_score <= -0.05:
        final_sentiment = "Negative"
    else:
        final_sentiment = "Neutral"

    bert_result = _bert_emotion(translated_text)
    emotion_scores = bert_result["scores"]
    final_emotion_label = bert_result["emotion"]
    emotion_confidence = bert_result["confidence"]

    if final_emotion_label == "Neutral" and final_sentiment == "Negative":
        final_emotion_label = "Sad"

    final_emotion = final_emotion_label
    recommendation = get_recommendation(final_emotion_label, emotion_confidence, final_sentiment, compound_score)

    return {
        "language_code": language,
        "detected_language": detected_language,
        "normalized_text": normalized_text,
        "cleaned_text": cleaned_text,
        "sentences": sentences,
        "original_tokens": original_tokens,
        "filtered_tokens": filtered_tokens,
        "emoji_list": emoji_list,
        "final_preprocessed_text": final_preprocessed_text,
        "translated_text": translated_text,
        "lemmatized_text": lemmatized_text,
        "sentiment_scores": sentiment_scores,
        "final_sentiment": final_sentiment,
        "emotion_scores": emotion_scores,
        "final_emotion": final_emotion,
        "emotion_confidence": emotion_confidence,
        "recommendation": recommendation,
    }

CRISIS_KEYWORDS = [
    "suicide", "kill myself", "end my life", "want to die", "self harm",
    "self-harm", "hurt myself", "not worth living", "no reason to live",
    "kill him", "kill her", "kill them", "kill my boss", "kill someone",
    "murder", "harm others", "hurt someone", "attack someone",
]

CRISIS_MESSAGE = (
    "I'm really glad you reached out, and I want to make sure you get support "
    "beyond what I can offer here. If you're in immediate danger, please contact "
    "your local emergency number right now. You can also reach a crisis line: "
    "in India, AASRA is available at +91-9820466726 (24/7). If you're outside "
    "India, please look up a local crisis helpline or talk to a trusted person "
    "or your HR/EAP contact. You don't have to go through this alone."
)

WELLNESS_SYSTEM_PROMPT = (
    "You are a supportive workplace wellness assistant for employees. "
    "Your role is to listen, validate feelings, and offer general, gentle "
    "coping suggestions (like breathing exercises, taking a short break, "
    "or talking to a trusted colleague or manager). "
    "You are NOT a therapist or doctor: never diagnose any condition, never "
    "claim expertise you don't have, and never give medical or medication "
    "advice. If the employee describes something serious (ongoing crisis, "
    "self-harm, harming others), gently encourage them to contact a mental "
    "health professional, their HR/EAP program, or a crisis helpline. "
    "Keep replies short (2-4 sentences), warm, and non-judgmental. "
    "Avoid clinical labels and avoid being preachy or repetitive."
)

def _contains_crisis_language(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in CRISIS_KEYWORDS)

def _generate_wellness_fallback(user_text: str) -> str:
    """Generate supportive, context-aware responses if offline or API is unavailable."""
    user_lower = user_text.lower().strip()

    # Calculate VADER sentiment score
    compound = 0.0
    try:
        vader = _get_vader()
        sentiment = vader.polarity_scores(user_text)
        compound = sentiment.get("compound", 0.0)
    except Exception:
        pass

    # Check for negation words
    negation_words = {
        "not", "no", "never", "hardly", "barely", "don't", "dont",
        "didn't", "didnt", "cannot", "can't", "cant", "won't", "wont",
        "isn't", "isnt", "aren't", "arent", "wasn't", "wasnt", "doesn't", "doesnt"
    }
    words = re.findall(r"\b\w+(?:'\w+)?\b", user_lower)
    has_negation = any(w in negation_words for w in words)

    sad_keywords = [
        "sad", "depress", "down", "unhappy", "cry", "lonel", "hopeless",
        "helpless", "worthless", "lost", "miserab", "grief", "pain",
        "hurting", "empty", "alone", "heartbreak", "struggl", "not okay",
        "not feeling good", "not good", "not well", "not feeling well",
        "low", "gloomy", "demotivat"
    ]
    stress_keywords = [
        "stress", "anxious", "overwhelm", "pressure", "burnout", "tired",
        "exhaust", "drained", "panic", "worry", "worried", "nervous",
        "tense", "overloaded", "hectic", "deadline"
    ]
    anger_keywords = [
        "angry", "frustrat", "annoy", "mad", "irritat", "furious", "upset",
        "hate", "resent", "unfair"
    ]
    positive_keywords = [
        "happy", "great", "good", "excit", "awesome", "proud", "relie",
        "joy", "wonderful", "fantastic", "amazing", "blessed", "peaceful", "cheerful"
    ]

    # 1. Hopelessness / Low mood / Sadness / Negated positive (e.g. "not feeling good", "not happy")
    if (
        any(k in user_lower for k in sad_keywords)
        or (has_negation and any(k in user_lower for k in positive_keywords))
        or (compound <= -0.25 and not any(k in user_lower for k in stress_keywords + anger_keywords))
    ):
        if any(h in user_lower for h in ["hopeless", "helpless", "worthless", "lost"]):
            return (
                "I hear how heavy and overwhelming things feel right now, and I want you to know you're not alone. "
                "Please remember to take things one gentle breath at a time without pressuring yourself. "
                "Would you like to talk about what has been weighing on you?"
            )
        return (
            "I hear you, and it's completely okay to have days where you're not feeling your best or things feel heavy. "
            "Take a slow breath and give yourself some space today. "
            "What's one small thing that might bring you a moment of comfort right now?"
        )

    # 2. Stress / Anxiety / Burnout / Overwhelm
    if any(k in user_lower for k in stress_keywords) or (compound <= -0.1 and "work" in user_lower):
        return (
            "It sounds like you've been carrying a lot of pressure and tension lately. "
            "Please consider pausing for just a minute to step away from your screen or try a 4-7-8 deep breathing exercise. "
            "Would you like to talk through what feels most urgent right now?"
        )

    # 3. Frustration / Anger
    if any(k in user_lower for k in anger_keywords):
        return (
            "That sounds really frustrating, and your feelings are completely valid. "
            "Taking a quick walk, drinking some cold water, or jotting down your thoughts can help release some of that tension. "
            "I'm right here if you'd like to vent."
        )

    # 4. Genuine positive (only if NO negation and sentiment is positive)
    if not has_negation and compound >= 0.05 and any(k in user_lower for k in positive_keywords):
        return (
            "I'm so glad to hear that! Celebrating positive moments and recognizing what went well is wonderful for your well-being. "
            "What made today feel especially good?"
        )

    # 5. General / Open fallback
    return (
        "Thank you for sharing that with me. I'm here to listen and support you. "
        "How has this been affecting your energy and peace of mind today?"
    )

def _get_hf_token() -> str:
    """Get HF token from Streamlit secrets or environment."""
    try:
        import streamlit as st
        token = st.secrets.get("HF_TOKEN", "")
        if token:
            return token
    except Exception:
        pass
    return os.environ.get("HF_TOKEN", "")

def _hf_api_reply(messages: list[dict]) -> str:
    """Call the HuggingFace Inference API trying supported serverless models with timeout."""
    hf_token = _get_hf_token()

    for model_name in PRIMARY_CHAT_MODELS:
        try:
            client = InferenceClient(
                model=model_name,
                token=hf_token or None,
                timeout=8,
            )
            response = client.chat_completion(
                messages=messages,
                max_tokens=150,
                temperature=0.7,
                top_p=0.9,
            )
            reply = response.choices[0].message.content.strip()
            if reply:
                return reply
        except Exception as e:
            print(f"[WellnessChat] Model '{model_name}' attempt skipped: {e}")
            continue

    return ""

def wellness_chat_reply(message: str, history: list[dict] | None = None) -> dict:
    if _contains_crisis_language(message):
        return {"reply": CRISIS_MESSAGE, "flagged": True}

    messages = [{"role": "system", "content": WELLNESS_SYSTEM_PROMPT}]
    for turn in (history or []):
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": message})

    # 1. Primary: Hugging Face Serverless Inference API with fallback across top models
    try:
        reply = _hf_api_reply(messages)
        if reply:
            return {"reply": reply, "flagged": False}
    except Exception as e:
        print(f"[WellnessChat] API note: {e}")

    # 2. Fast, empathetic fallback (context-aware, negation-aware sentiment fallback)
    return {
        "reply": _generate_wellness_fallback(message),
        "flagged": False,
    }

