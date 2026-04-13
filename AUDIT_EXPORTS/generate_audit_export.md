# How to Generate a POLYGOD Backend Audit Export

## IMPORTANT — Two Different Systems

This file is a DEVELOPER WORKFLOW TOOL.
It has nothing to do with `src/backend/snapshot_engine.py`.

| System | What it is | When it runs |
|--------|-----------|--------------|
| `src/backend/snapshot_engine.py` | Runtime Python class — checkpoints LangGraph state, commits code to git during live trading | Automatically, called by polygod_graph.py and Telegram /snapshot command |
| This file (`generate_audit_export.md`) | A prompt you paste into your agent to export the codebase as a text file for Claude to review | Manually, by a human, at the end of a dev session |

Never ask an agent to "run the snapshot engine" when you mean "generate an
audit export". Use the exact phrase "generate an audit export" or "run the
audit export prompt" to avoid confusion.

---

## How to Use This File

1. Copy everything between the dashed lines below
2. Paste it into your VS Code agent chat
3. The agent will output the full codebase as a single text block
4. Save that output as: AUDIT_EXPORTS/backend_audit_YYYY-MM-DD.txt
5. Commit and push (commands at the bottom of this file)
6. Upload the .txt file to Claude in the next audit session

---

## AUDIT EXPORT PROMPT
## (copy everything between the lines below and paste into your agent)

--------------------------------------------------------------------------------
I need you to generate a clean, single-text audit export of the backend only
from the POLYGOD project folder.

Please structure the output exactly like this:

1. Directory Tree
   (root level + full src/backend/ tree including all subfolders)

2. Root Configuration & Docs (in this order):
   - pyproject.toml
   - docker-compose.yml
   - docker-compose_prod.yml
   - AGENTS.md

3. Core Backend Files (in this exact order):
   - src/backend/main.py
   - src/backend/config.py
   - src/backend/database.py
   - src/backend/db_models.py

4. Routes (all files inside src/backend/routes/):
   - src/backend/routes/__init__.py
   - src/backend/routes/markets.py
   - src/backend/routes/news.py
   - src/backend/routes/debate.py
   - src/backend/routes/users.py
   - src/backend/routes/llm.py
   - src/backend/routes/telegram.py

5. Key Modules (all files inside each folder/path):
   - src/backend/polymarket/__init__.py
   - src/backend/polymarket/client.py
   - src/backend/polymarket/schemas.py
   - src/backend/news/__init__.py
   - src/backend/news/aggregator.py
   - src/backend/news/schemas.py
   - src/backend/tasks/__init__.py
   - src/backend/tasks/update_markets.py
   - src/backend/services/__init__.py
   - src/backend/services/llm_concierge.py
   - src/backend/agents/debate.py
   - src/backend/strategies/micro_niche_strategy.py
   - src/backend/middleware/__init__.py
   - src/backend/middleware/auth.py
   - src/backend/middleware/rate_limit.py
   - src/backend/middleware/security_headers.py
   - src/backend/models/__init__.py
   - src/backend/models/llm.py
   - src/backend/cache.py
   - src/backend/auth.py
   - src/backend/llm_router.py
   - src/backend/polygod_graph.py
   - src/backend/self_improving_memory_loop.py
   - src/backend/snapshot_engine.py
   - src/backend/whale_copy_rag.py
   - src/backend/autoresearch_lab.py
   - src/backend/niche_scanner.py
   - src/backend/parallel_tournament.py

Use this exact format for every file:

=== FILE: src/backend/main.py ===
<full raw code here — no omissions, no truncation>

Rules:
- Include EVERY Python file listed above with complete raw content.
- Do NOT summarise, truncate, or add "... rest of file ..." anywhere.
- Do NOT include frontend/, node_modules/, qdrant_storage/, .git/, or AUDIT_EXPORTS/.
- File paths must be relative to the repo root.
- Start with the directory tree, then follow the exact order above.
- At the very end, add this footer:
  "Audit export generated on [TODAY'S DATE]. Backend audit export."

Now generate the full audit export.
--------------------------------------------------------------------------------

---

## After the agent generates the audit export

1. Save the output as:
   AUDIT_EXPORTS/backend_audit_YYYY-MM-DD.txt
   (use today's date, e.g. AUDIT_EXPORTS/backend_audit_2026-04-13.txt)

2. Commit and push:
   git add AUDIT_EXPORTS/backend_audit_YYYY-MM-DD.txt
   git commit -m "audit-export: backend audit YYYY-MM-DD"
   git push

3. Upload the .txt file to Claude for the next audit session.
