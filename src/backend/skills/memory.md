# SKILL: MEMORY SYSTEMS

## Two Memory Systems in POLYGOD

### Mem0 (Trading Memory)
- WHAT: Trade decisions, agent verdicts, PnL outcomes, whale patterns
- WHERE: Qdrant vector store at http://qdrant:6333
- WHEN: Written automatically by remember_node() on every agent execution
- HOW TO QUERY:
```python
from src.backend.polygod_graph import mem0_search
results = mem0_search("winning trades weather markets", user_id="polygod")
```
- HOW TO ADD:
```python
from src.backend.polygod_graph import mem0_add
mem0_add("Market XYZ: bought YES at 35%, resolved YES. Thesis: underpriced political risk.", user_id="polygod")
```

### MemPalace (Project Memory)
- WHAT: Architecture decisions, bug fixes, operator preferences, session history
- WHERE: ~/.mempalace/palace/ (ChromaDB local)
- WHEN: Written during save hooks, manually via CLI or MCP tools
- HOW TO QUERY (via MCP tool):
  mempalace_search("why did we use SQLite", wing="polygod")
- HOW TO ADD (via MCP tool):
  mempalace_add_drawer(content, wing="polygod", room="architecture")
- HOW TO SEARCH ACROSS EVERYTHING:
  mempalace_search("auth fix") — searches all wings

## MemPalace Wings Setup for POLYGOD
wing_polygod    → the trading system itself (architecture, bugs, decisions)
wing_markets    → individual market analysis and outcomes
wing_operator   → your preferences as the human operator
wing_errors     → error patterns and their fixes

## Memory Priority Rules
1. Critical trading decisions → Mem0 (fast retrieval in agent context)
2. Architecture/system knowledge → MemPalace (searchable across sessions)
3. Error patterns → BOTH (Mem0 for pattern matching, MemPalace for full context)
4. Operator preferences → MemPalace wing_operator

## Forgetting Engine
Runs every 6 hours. TTL tiers:
- high_utility (pnl > 0, confidence > 80%): 90 days
- medium: 30 days
- low (debug noise): 7 days
To preserve something: add metadata tier="high_utility" when calling mem0.add()
