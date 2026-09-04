#!/usr/bin/env bash
# voltpulse-backend/dev.sh

set -e

# Ensure clean termination of all child background processes on exit
cleanup() {
    echo ""
    echo "========================================="
    echo " Shutting down VoltPulse Engine services..."
    echo "========================================="
    kill $(jobs -p) 2>/dev/null || true
    wait 2>/dev/null || true
    echo "All processes stopped cleanly."
}

trap cleanup EXIT INT TERM

# 1. Verify Docker backing services
echo "Verifying PostgreSQL and Redis containers..."
docker compose up -d postgres redis

# 2. Activate Virtual Environment
source .venv/bin/activate

# 3. Start the FastAPI ASGI Gateway
echo "Starting FastAPI Ingestion Gateway on :8000..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 4. Start the Database Stream Persister Worker
echo "Starting Stream Ingestion Persister Worker..."
python -m app.workers.stream_consumer &

# 5. Start the Anomaly & Rules Evaluator Worker
echo "Starting Anomaly & Rules Evaluator Worker..."
python -m app.workers.anomaly_consumer &

echo "========================================="
echo " VoltPulse Engine is running live!"
echo " Press Ctrl+C in this terminal to stop all."
echo "========================================="

# Keep the parent script alive
wait