#Site Live at:
https://moodmentorforemployees-jsmtrj27vkvgyxoujx6pnn.streamlit.app/
---
title: MoodMentor
emoji: 🧘
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

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
- **Frontend**: Streamlit
- **Backend**: FastAPI
- **NLP**: HuggingFace Transformers (BERT GoEmotions + Qwen 2.5 0.5B), VADER, spaCy
- **Database**: PostgreSQL (Neon)

## Environment Variables / Secrets
Set these secrets in Hugging Face Space Settings (or `.env` locally):

| Variable | Description | Example / Default |
|---|---|---|
| `DB_HOST` | Neon / Postgres host | `ep-xyz.us-east-2.aws.neon.tech` |
| `DB_NAME` | Database name | `neondb` |
| `DB_USER` | Database user | `neondb_owner` |
| `DB_PASSWORD` | Database password | `your_db_password` |
| `DB_PORT` | Database port (optional) | `5432` |
| `JWT_SECRET` | Secret key for JWT session tokens | `your_random_secret_string` |
| `SMTP_EMAIL` | Gmail address for sending OTP emails | `your-email@gmail.com` |
| `SMTP_APP_PASSWORD` | Google App Password (16-character) | `xxxx xxxx xxxx xxxx` |
| `BACKEND_URL` | Backend URL for Streamlit frontend | `http://localhost:8000` (default inside Docker) |
| `ALLOWED_ORIGINS`| CORS allowed origins for FastAPI | `*` (default) |
