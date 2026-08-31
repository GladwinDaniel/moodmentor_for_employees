FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download xx_sent_ud_sm

# Copy all application source files
COPY db.py auth.py email_utils.py security.py nlp_pipeline.py \
     recommendations.py backend.py app.py ./

# Copy startup script
COPY start.sh .
RUN chmod +x start.sh

# Hugging Face Spaces expects port 7860
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["./start.sh"]
