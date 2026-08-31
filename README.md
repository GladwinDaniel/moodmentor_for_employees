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
