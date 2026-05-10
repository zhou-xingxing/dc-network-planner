#!/bin/bash
# Start the DC Network Planner backend server
cd "$(dirname "$0")"

# Create virtual environment if needed
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install -e .
else
    source venv/bin/activate
fi

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
