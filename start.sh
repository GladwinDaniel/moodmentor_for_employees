#!/bin/bash
set -e

echo "=== MoodMentor: Initializing database ==="
python -c "from db import init_db; init_db(); print('Database tables ready.')"

echo "=== MoodMentor: Starting FastAPI backend on port 8000 ==="
uvicorn backend:app --host 0.0.0.0 --port 8000 &

# Wait for backend to be ready
echo "Waiting for backend..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "Backend is ready!"
        break
    fi
    sleep 1
done

echo "=== MoodMentor: Starting Streamlit frontend on port 7860 ==="
exec streamlit run app.py \
    --server.port 7860 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false \
    --server.fileWatcherType none
