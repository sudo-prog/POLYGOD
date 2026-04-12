# How to Generate a POLYGOD Backend Snapshot

Copy and paste the prompt below directly into your agent chat box.
The agent will generate a single text document you can save to this folder.

---

## SNAPSHOT PROMPT (copy everything between the lines)

────────────────────────────────────────────────────────────
I need you to generate a clean, single-text snapshot of the backend only
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
- Do NOT include frontend/, node_modules/, qdrant_storage/, .git/, or SNAPSHOTS/.
- File paths must be relative to the repo root.
- Start with the directory tree, then follow the exact order above.
- At the very end, add this footer:
  "Snapshot generated on [TODAY'S DATE]. Backend audit snapshot."

Now generate the full snapshot.
────────────────────────────────────────────────────────────

---

## After the agent generates the snapshot:

1. Save the output as:
   SNAPSHOTS/backend_snapshot_YYYY-MM-DD.txt
   (use today's date, e.g. SNAPSHOTS/backend_snapshot_2026-04-10.txt)

2. Commit and push:
   git add SNAPSHOTS/backend_snapshot_YYYY-MM-DD.txt AGENT_NOTES.md
   git commit -m "snapshot: backend audit snapshot YYYY-MM-DD"
   git push

3. Share the snapshot file with Me for the next audit session.
