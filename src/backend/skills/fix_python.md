# SKILL: FIX_PYTHON

## Your Debugging Protocol
1. Parse full stack trace — identify the EXACT line, not just the exception type
2. Check if it's an import error → circular import? missing __init__.py? wrong package name?
3. Check if it's async/await → missing await? calling coroutine without await? sync in async context?
4. Check if it's a Pydantic v2 issue → SecretStr needs .get_secret_value(), ConfigDict not class Config
5. Check if it's a SQLAlchemy session issue → session closed? outside async context? wrong pool for SQLite?
6. Generate minimal fix — change as few lines as possible
7. Check: does fix break any other imports or callers?
8. If it's a regression, write a test

## POLYGOD-Specific Known Traps

### Circular imports
```python
# BAD — often causes ImportError at startup
from src.backend.polygod_graph import something  # in database.py

# GOOD — lazy import inside function
async def my_func():
    from src.backend.polygod_graph import something
```

### SecretStr comparison (always fails silently)
```python
# BAD — SecretStr object is always truthy
if settings.GEMINI_API_KEY:

# GOOD
if settings.GEMINI_API_KEY.get_secret_value():
```

### SQLite locked under load
```python
# BAD — pool_size not valid for SQLite
create_async_engine(url, pool_size=20)

# GOOD — use StaticPool for SQLite
create_async_engine(url, poolclass=StaticPool, connect_args={"check_same_thread": False})
```

### Async session used after close
```python
# BAD
session = async_session_factory()
await session.execute(...)
# ... later ...
await session.execute(...)  # session may be closed

# GOOD — always use as context manager
async with async_session_factory() as session:
    await session.execute(...)
```

### mem0 import (common wrong import)
```python
# BAD
from mem0 import Mem0

# GOOD
from mem0 import Memory as _Mem0Memory
```

## File Map for Common Errors
- "No module named src.backend" → PYTHONPATH issue → set PYTHONPATH=. in .env
- "database is locked" → database.py → check StaticPool + check_same_thread
- "ENCRYPTION_KEY not valid Fernet" → config.py → generate with Fernet.generate_key()
- "double prefix 404" → routes/debate.py or routes/users.py → remove prefix from APIRouter()
- "checkpointer ProgrammingError" → polygod_graph.py → don't close the sqlite3 conn
- "circuit breaker open" → news/aggregator.py → wait 30min or check NEWS_API_KEY
