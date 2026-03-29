# CLINE BUILD MANIFEST — POLYGOD

**STATUS**: Ready for Cline to execute
**BRANCH**: Initialize as `main`
**GOAL**: Complete, tested, production-ready polymarket terminal with POLYGOD brain

---

## EXECUTION CHECKLIST

### ✅ Phase 1: Clone & Initialize (DO THIS FIRST)

```bash
# Already done: git init + local config
# Now clone the base repo:
cd /home/thinkpad/projects/POLYGOD
git clone https://github.com/luuisotorres/polymarket-intelligence.git .

# Copy environment template
cp .env.example .env 2>/dev/null || echo "# Create .env manually with keys below"
```

**ENV VARS TO ADD** (append to .env):

```
POLYGOD_MODE=0
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
DEXTER_PATH=../dexter
```

---

### ✅ Phase 2: Install Dependencies

```bash
# Backend
cd backend
pip install -r requirements.txt --upgrade
pip install pydantic python-dotenv lru-dict

# Frontend
cd ../frontend
npm install
```

---

### ✅ Phase 3: Create POLYGOD Brain Files

**FILE: `backend/src/polygod_graph.py`**

- Full LangGraph swarm with:
  - Research node (web search, news, whale alerts)
  - Mode router (paper trading / strategy select / sim mode)
  - Execute node (strategy chain)
  - Paper trading mirror (live paper PnL tracking)
  - Mem0 integration (persistent memory)
  - Critic node (risk review before execute)
  - Consult Dexter tool (strategy suggestion)
- Must include `/health` endpoint check
- WebSocket support for live state streaming

**FILE: `backend/main.py` (UPGRADE existing)**

- Import POLYGOD graph app
- Add WebSocket route: `/ws/polygod`
- Stream: `paper_pnl`, `mode`, `whale_alerts`, `strategy_state`
- Graceful error handling + fallback to paper trading

**FILE: `backend/.env.example`**

```
POLYMARKET_API_KEY=
NEWSAPI_KEY=
GEMINI_API_KEY=
TAVILY_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
POLYGOD_MODE=0
DEXTER_PATH=../dexter
```

**FILE: `frontend/src/PolyGodDashboard.tsx`**

- Real-time WebSocket connection to `/ws/polygod`
- Display: mode indicator (Sim/Paper/Live), P&L curve, whale alerts
- Strategy selector dropdown
- Risk limits panel (max per bot, global kill switch)
- Charts: P&L, position history, backtest overlay

**FILE: `.gitignore`** (if not present)

```
.env
.env.local
node_modules/
__pycache__/
*.pyc
.DS_Store
.vscode/
dist/
build/
*.log
.next/
.turbo/
backend/venv/
```

---

### ✅ Phase 4: Test & Validate

```bash
# Backend health check
cd backend
python -m pytest tests/ -v 2>/dev/null || echo "No tests yet"
python main.py &  # Start in background

# Check health
curl http://localhost:8000/health

# Frontend build
cd ../frontend
npm run build

# Verify no build errors
echo "Build complete!"
```

---

### ✅ Phase 5: Git Commit & Ready for Push

```bash
cd /home/thinkpad/projects/POLYGOD
git add -A
git commit -m "feat: initialize polymarket with POLYGOD brain integration

- Clone polymarket-intelligence base repo
- Integrate LangGraph POLYGOD swarm (research, mode router, execute, paper mirror)
- Add WebSocket live state streaming
- Build React dashboard with P&L tracking and whale alerts
- Paper-trading-first safety model
- Mem0 persistent memory integration"

git branch -m master main
```

---

## KNOWN ISSUES & SOLUTIONS

| Issue                               | Solution                                              |
| ----------------------------------- | ----------------------------------------------------- |
| Clone fails (dir not empty)         | Folder already cleared; should work now               |
| Missing .env.example in cloned repo | Create manually with vars listed above                |
| Python version mismatch             | Use Python 3.10+                                      |
| npm install fails                   | Try `npm cache clean --force && npm install`          |
| Backend won't start                 | Check port 8000 is free; verify `python main.py` runs |

---

## SUCCESS CRITERIA

- ✅ All files clone successfully
- ✅ Dependencies install without errors
- ✅ Backend starts on `localhost:8000`
- ✅ `/health` endpoint returns `{"status": "ok"}`
- ✅ `/ws/polygod` WebSocket connects
- ✅ Frontend builds without errors
- ✅ Git repo initialized with clean history on `main` branch
- ✅ Ready for `git push origin main` (once remote is configured)

---

## NEXT STEPS (after Cline completes this)

1. GitHub repo created: `POLYGOD`
2. Remote configured: `https://github.com/sudo-prog/POLYGOD.git`
3. Push: `git push -u origin main`
4. Update `COORDINATION_BOARD.md` with branch + PR link

---

**Cline: Execute this in order. Stop at first error and report. Good luck!**
