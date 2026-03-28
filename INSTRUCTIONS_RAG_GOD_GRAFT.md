# RAG_GOD GRAFT INSTRUCTIONS — FOR CLINE (1M CONTEXT)

MISSION: Inject full RAG_GOD brain into the existing polymarket-intelligence codebase.

## Step 1: Create backend/src/rag_god_graph.py
Paste the complete cyclic swarm code (research_node, mode_router with modes 0-3, approve_node, risk_gate_node with Kelly guard, execute_node with live + paper shadow, critic_node, consult_dexter tool, Mem0 writes on every edge, PaperMirror class).

## Step 2: Upgrade backend/main.py
Add at top:
from rag_god_graph import rag_god_app, paper, MODE

Mount the graph:
app.mount("/rag-god", rag_god_app)

Add WebSocket for live stream:
@app.websocket("/ws/rag-god")
async def rag_god_ws(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_json({
            "paper_pnl": paper.pnls[-1] if paper.pnls else 0,
            "mode": MODE,
            "whale_alert": "HorizonSplendidView just loaded 150k YES — RAG_GOD analyzing"
        })
        await asyncio.sleep(2)

Add endpoint:
@app.post("/rag-god/switch-mode")
async def switch_mode(new_mode: int):
    global MODE
    MODE = new_mode
    return {"status": f"Mode {MODE} — {'BEAST MODE' if MODE == 3 else 'safe'}"}

## Step 3: Frontend hook — create frontend/src/hooks/useRAGGodWS.ts
Paste the hook code that connects to ws://localhost:8000/ws/rag-god and updates Zustand store (paper_pnl, mode, alerts). Import and call it in the main dashboard / Whale List / Debate Floor components.

## Step 4: Update docker-compose.yml
Add volume for Mem0 (Qdrant) and ensure backend runs the upgraded main.py.

## Step 5: Update .env.example
Add:
RAG_GOD_MODE=0
MEM0_CONFIG={"provider": "qdrant", "vector_store": {"url": "http://qdrant:6333"}}

## Step 6: Zero-Error Verification
- Run `docker compose up --build`
- Check logs for zero errors
- curl http://localhost:8000/rag-god/status
- Test mode switch in frontend
- Confirm paper mirror is shadowing every decision
- Fix any issues line-by-line until clean

## Step 7: Push to New Repo
- git add .
- git commit -m "GOD TIER: Full RAG_GOD brain grafted into polymarket-intelligence base"
- Create new GitHub repo "rag-god-terminal" and push
- Share the new repo link for final verification.
