# SKILL: SELF_HEAL

Autonomous error diagnosis and repair protocol.
Run this when an error is detected. Check MemPalace first. Act second.

## DIAGNOSIS FLOW

```
ERROR DETECTED
    ↓
1. Parse error type (ImportError? SQLError? HTTPError? etc.)
    ↓
2. Check MemPalace wing_errors for known fix
    ↓ (if found)
    Apply known fix immediately
    ↓ (if not found)
3. Classify severity
    ↓
4. Apply automated fix if confidence > 80%
    ↓
5. Verify fix worked
    ↓
6. Store fix to MemPalace for next time
    ↓
7. Alert operator on Telegram if Critical
```

## ERROR CLASSIFICATION

### CRITICAL (fix immediately, alert operator)
- Database connection lost
- All LLM providers failing
- CLOB API unreachable in MODE 3
- Memory exhaustion (RAM > 95%)
- Checkpointer closed/unavailable

### HIGH (fix within 5 minutes, log prominently)
- Single LLM provider failing (has fallbacks)
- NewsAPI circuit breaker open
- Scheduler not running
- WebSocket handler crashing

### MEDIUM (log, fix at next opportunity)
- Telegram bot command failing
- Non-critical background task failing
- Slow response times

### LOW (log only)
- Missing optional feature (Playwright, GPU)
- Rate limit hit on non-critical API

## KNOWN FIXES (apply without asking)

### "Cannot connect to database"
```python
# Check 1: Is postgres running?
subprocess.run(["docker", "compose", "ps", "postgres"])
# Fix: restart postgres
subprocess.run(["docker", "compose", "restart", "postgres"])
await asyncio.sleep(5)
await init_db()
```

### "Circuit breaker open" (NewsAPI)
```python
# Just wait — will auto-heal in 30min
# Or force-reset:
from src.backend.news.aggregator import news_breaker
# aiobreaker 1.x: create a fresh breaker (old one is stuck)
from aiobreaker import CircuitBreaker
from datetime import timedelta
import src.backend.news.aggregator as na
na.news_breaker = CircuitBreaker(fail_max=3, timeout_duration=timedelta(minutes=30))
```

### "No module named 'X'"
```python
import subprocess
# Try to install missing package
subprocess.run(["uv", "add", "X"], check=True)
# Or: subprocess.run(["pip", "install", "X", "--break-system-packages"])
```

### "ENCRYPTION_KEY not valid"
```python
from cryptography.fernet import Fernet
new_key = Fernet.generate_key().decode()
# Write to .env:
with open(".env", "a") as f:
    f.write(f"\nENCRYPTION_KEY={new_key}\n")
# Warn: existing encrypted keys are now unreadable
```

### "polygod-swarm running out of memory"
```python
subprocess.run(["docker", "compose", "stop", "polygod-swarm"])
subprocess.run(["docker", "update", "--memory=4g", "--memory-swap=4g", "polygod-swarm-1"])
```

### "Rate limit exceeded" (LLM API)
```python
import src.backend.services.llm_concierge as lc
lc._RPM_LIMIT = max(10, getattr(lc, '_RPM_LIMIT', 60) // 2)
# Halve the rate limit until it recovers
```

## POST-FIX VERIFICATION CHECKLIST
1. curl http://localhost:8000/api/health → {"status": "god-tier"}
2. Check scheduler.running == True
3. Check at least 1 LLM provider healthy
4. Check DB connected in health response
5. If MODE >= 2: check CLOB API reachable
6. Store fix to MemPalace: await mempalace_bridge.remember_error(error, fix, component)
