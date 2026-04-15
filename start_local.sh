#!/bin/bash
set -e

echo "Starting POLYGOD locally..."

# Start infrastructure (postgres, qdrant, redis)
echo "Starting Docker services..."
docker compose up -d postgres qdrant redis
echo "Waiting for services to be ready..."
sleep 5

# Run database migrations
echo "Running migrations..."
source venv/bin/activate || python -m venv venv && source venv/bin/activate
pip install -e ".[dev]" -q
alembic upgrade head || python -c "
import asyncio
from src.backend.database import init_db
import os; os.environ['DEBUG'] = 'True'
asyncio.run(init_db())
print('Tables created.')
"

# Start backend
echo "Starting backend on http://localhost:8000 ..."
uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Start frontend
echo "Starting frontend on http://localhost:5173 ..."
cd frontend 2>/dev/null || true
npm install -q
npm run dev &
FRONTEND_PID=$!

echo ""
echo "POLYGOD is running:"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop everything."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; docker compose stop postgres qdrant redis" EXIT
wait
