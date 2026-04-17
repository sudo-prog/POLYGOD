#!/bin/bash
# Migration script that respects DEBUG mode
set -e

echo "Checking DEBUG mode..."

# Check if we're in DEBUG mode
if uv run python -c "
from src.backend.config import settings
print('DEBUG mode:', settings.DEBUG)
exit(0 if settings.DEBUG else 1)
" 2>/dev/null; then
    echo "DEBUG=True: Using create_all for development..."
    uv run python -c "
import asyncio
from src.backend.database import init_db
asyncio.run(init_db())
print('Database initialized with create_all')
"
else
    echo "DEBUG=False: Checking for migrations..."

    # Check if alembic_version table exists
    if uv run python -c "
import asyncio
from sqlalchemy import text
from src.backend.database import engine

async def check():
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(\"SELECT 1 FROM alembic_version LIMIT 1\"))
            return True
    except:
        return False

result = asyncio.run(check())
print(f'Migrations applied: {result}')
exit(0 if result else 1)
" 2>/dev/null; then
        echo "Migrations already applied, skipping..."
    else
        echo "Running migrations..."
        uv run alembic upgrade head
    fi
fi

echo "Starting uvicorn..."
export PYTHONPATH=/app:$PYTHONPATH
exec uv run uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 --workers 4
