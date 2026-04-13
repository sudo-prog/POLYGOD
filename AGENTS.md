# POLYGOD Agent Instructions

## Core Session Protocol

**BEFORE any task:** Read this file and verify all instructions are followed.

**END OF EVERY SESSION:** 
When ALL tasks are 100% complete, update AGENT_NOTES.md with a log entry for the changes made in that session. Use the existing format with Date, Agent, and Changes Made columns.

### Session Log Format
```
| Date       | Agent  | Changes Made                                              |
|------------|--------|-----------------------------------------------------------|
```

### Update Requirements
- Add new entries at the top of the session log (after the header row)
- Include the current date (YYYY-MM-DD)
- Agent should be "Kilo (GOD TIER ENGINEER)" or similar
- Changes Made should be a concise summary of what was done
- Reference specific files changed when applicable

## Project-Specific Rules

### Code Standards
- All TypeScript/React code follows the existing patterns in the codebase
- WebSocket connections use first-message auth pattern (token in JSON, not URL)
- Components follow the existing UI patterns (ios-* classes, tailwind)

### Communication
- Be direct and technical, not conversational
- Never end with a question or offer for further assistance
- Complete one todo before starting another

## AUDIT EXPORT PROMPT

I need you to generate a clean, single-text audit export of the backend only
from the POLYGOD project folder.
Please structure the output exactly like this:

Directory Tree
(root level + full src/backend/ tree including all subfolders)
Root Configuration & Docs (in this order):

pyproject.toml
docker-compose.yml
docker-compose_prod.yml
AGENTS.md


Core Backend Files (in this exact order):

src/backend/main.py
src/backend/config.py
src/backend/database.py
src/backend/db_models.py


Routes (all files inside src/backend/routes/):

src/backend/routes/__init__.py
src/backend/routes/markets.py
src/backend/routes/news.py
src/backend/routes/debate.py
src/backend/routes/users.py
src/backend/routes/llm.py
src/backend/routes/telegram.py


Key Modules (all files inside each folder/path):

src/backend/polymarket/__init__.py
src/backend/polymarket/client.py
src/backend/polymarket/schemas.py
src/backend/news/__init__.py
src/backend/news/aggregator.py
src/backend/news/schemas.py
src/backend/tasks/__init__.py
src/backend/tasks/update_markets.py
src/backend/services/__init__.py
src/backend/services/llm_concierge.py
src/backend/agents/debate.py
src/backend/strategies/micro_niche_strategy.py
src/backend/middleware/__init__.py
src/backend/middleware/auth.py
src/backend/middleware/rate_limit.py
src/backend/middleware/security_headers.py
src/backend/models/__init__.py
src/backend/models/llm.py
src/backend/cache.py
src/backend/auth.py
src/backend/llm_router.py
src/backend/polygod_graph.py
src/backend/self_improving_memory_loop.py
src/backend/snapshot_engine.py
src/backend/whale_copy_rag.py
src/backend/autoresearch_lab.py
src/backend/niche_scanner.py
src/backend/parallel_tournament.py



Use this exact format for every file:
=== FILE: src/backend/main.py ===
<full raw code here — no omissions, no truncation>
Rules:

Include EVERY Python file listed above with complete raw content.
Do NOT summarise, truncate, or add "... rest of file ..." anywhere.
Do NOT include frontend/, node_modules/, qdrant_storage/, .git/, or AUDIT_EXPORTS/.
File paths must be relative to the repo root.
Start with the directory tree, then follow the exact order above.
At the very end, add this footer:
"Audit export generated on [TODAY'S DATE]. Backend audit export."

Now generate the full audit export.

After the agent generates the audit export

✅ ALWAYS COMMIT AND PUSH IMMEDIATELY AFTER GENERATING AUDIT EXPORT:
1. Save the output as:
   AUDIT_EXPORTS/backend_audit_YYYY-MM-DD.txt
   (use today's date, e.g. AUDIT_EXPORTS/backend_audit_2026-04-13.txt)

2. Run these commands BEFORE doing ANYTHING ELSE:
   ```bash
   git add AUDIT_EXPORTS/backend_audit_YYYY-MM-DD.txt
   git commit -m "audit-export: backend audit YYYY-MM-DD"
   git push
   ```

3. Then:
   - Update AGENT_NOTES.md with session log entry
   - Commit and push AGENT_NOTES.md
   - Upload the .txt file to Claude for the next audit session.

✅ NEVER skip the git push step. Audit exports must be immediately persisted to remote git.
-------- END OF FILE --------
