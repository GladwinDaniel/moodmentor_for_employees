#Site Live at:
https://moodmentorforemployees.streamlit.app/

# MoodMentor – AI-Powered Employee Wellness Platform

An intelligent employee mental health and wellness platform powered by NLP and AI.

## Features
- 🎭 **Mood Tracking** – Daily mood logging with emoji selection
- 📝 **AI Journal Analysis** – Multilingual NLP sentiment & emotion detection
- 🤖 **Wellness Chat Assistant** – AI-powered mental health chatbot (Qwen 0.5B)
- 📊 **Analytics Dashboard** – Visual mood trends with charts & PDF reports
- 📋 **Mental Health Questionnaires** – PHQ-9 and GAD-7 assessments
- 👥 **HR Manager View** – Aggregated team wellness insights
- 🔐 **Secure Auth** – JWT + OTP email verification

## Tech Stack
- **Framework**: Streamlit
- **NLP**: HuggingFace Transformers (BERT GoEmotions + Qwen 2.5 0.5B), VADER, spaCy
- **Database**: PostgreSQL (Neon)

## Secrets / Environment Variables
Configure these in Streamlit Cloud Secrets (or `.env` locally / Hugging Face Secrets):

| Variable | Description |
|---|---|
| `DB_HOST` | Neon PostgreSQL host |
| `DB_NAME` | Database name (`neondb`) |
| `DB_USER` | Database user (`neondb_owner`) |
| `DB_PASSWORD` | Neon database password |
| `DB_PORT` | `5432` |
| `JWT_SECRET` | Secret key for JWT session tokens |
| `SMTP_EMAIL` | Gmail address for sending OTP emails |
| `SMTP_APP_PASSWORD` | Google App Password |
