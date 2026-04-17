# SKILL: EMERGENCY_PLAYBOOK

When everything is on fire. Stay calm. Follow this.

## SEVERITY LEVELS

### 🔴 LEVEL 1 — SYSTEM DOWN (respond within 2 minutes)
Backend container crashed, database unreachable, all services down.

**Immediate actions:**
```bash
# 1. Check what's actually down
docker compose ps

# 2. Check logs for crash reason
docker compose logs backend --tail=50

# 3. Restart in order (dependencies first)
docker compose restart postgres
sleep 5
docker compose up -d redis qdrant
sleep 5
docker compose up -d backend

# 4. Verify health
curl http://localhost:8000/api/health
```

### 🟠 LEVEL 2 — RUNAWAY PROCESS (respond within 5 minutes)
CPU/RAM spike, process not responding, tournaments stuck.

**Immediate actions:**
```bash
# 1. Identify the culprit
docker stats --no-stream

# 2. Stop the heavy process
docker compose stop polygod-swarm

# 3. Kill hanging Python processes
pkill -f "parallel_tournament"
pkill -f "autoresearch"

# 4. Set resource limits
docker update --memory=4g --memory-swap=4g polygod-backend-1

# 5. Reduce mode if in BEAST
# Via Telegram: /mode 0
```

### 🟡 LEVEL 3 — LLM OUTAGE (respond within 15 minutes)
All AI providers failing, no completions possible.

**Immediate actions:**
1. Check GEMINI_API_KEY not expired → Google AI Studio
2. Check GROQ_API_KEY → console.groq.com
3. Fallback to Puter (no key needed): check llm_router.py puter endpoint
4. Set mode to 0 (OBSERVE) until resolved: `/mode 0`
5. LiteLLM fallback list in llm_router.py — verify model names still correct

### 🟢 LEVEL 4 — DEGRADED (respond within 1 hour)
One non-critical service down, app still functional.

**Services and their degraded-mode impact:**
- Qdrant down → WhaleCopyRAG disabled, Mem0 fails → core trading still works
- Redis down → rate limiting disabled → increase slowapi limits manually
- Telegram down → no alerts/commands → use HTTP API directly
- NewsAPI down → news feed empty → circuit breaker will auto-recover
- Playwright down → web search disabled → Tavily still works

## ROLLBACK PROCEDURE
```bash
# List recent snapshots
# Via Telegram: /snapshots

# Rollback to last known state
# Via Telegram: /rollback <sha>

# If Telegram is also down:
cd /path/to/polygod
git log --oneline --grep="SNAPSHOT" | head -5
git checkout <sha>
docker compose up --build -d backend
```

## NEVER DO THESE IN AN EMERGENCY
- Don't restart ALL containers simultaneously (cascading startup failures)
- Don't wipe the database to "fix" connection issues
- Don't generate a new ENCRYPTION_KEY (will destroy all stored API keys)
- Don't kill the postgres container with volume removal
- Don't push untested code to fix a production issue

## CONTACTS / RESOURCES
- Polymarket status: https://status.polymarket.com
- Gemini status: https://status.cloud.google.com
- Groq status: https://status.groq.com
- LiteLLM docs: https://docs.litellm.ai
