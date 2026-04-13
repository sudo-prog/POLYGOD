# POLYGOD User Manual

**Version:** 1.0
**Last Updated:** April 2026
**Platform:** Web Application (Polymarket Intelligence Dashboard)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Key Features](#key-features)
3. [Quick Guide - Screen Elements](#quick-guide---screen-elements)
4. [Setup Instructions](#setup-instructions)
5. [FAQ Section](#faq-section)
6. [Missing & Needed Features](#missing--needed-features)

---

## 1. Introduction

POLYGOD is an AI-powered real-time market intelligence dashboard for Polymarket prediction markets. It provides comprehensive market analysis, whale tracking, news aggregation, and AI-driven debate capabilities to help traders make informed decisions.

**Target Users:**
- Prediction market traders
- Data-driven investors
- Market analysts
- AI enthusiasts exploring decentralized markets

---

## 2. Key Features

### 2.1 Top 100 Markets Dashboard
Browse the most active Polymarket markets sorted by 7-day trading volume. Each market displays:
- Current probability (Yes/No percentages)
- 24-hour trading volume
- Price change indicators (bullish/bearish)

### 2.2 Live Price Charts
Interactive charts powered by Polymarket CLOB API featuring:
- Real-time price history updates
- Multiple timeframe options: 24H, 7D, 1M, ALL
- Candlestick and line chart views

### 2.3 Related News Feed
Aggregated news articles from NewsAPI relevant to selected markets. Stay informed about events that may impact market outcomes.

### 2.4 Whale Order Tracking
Monitor large trades (orders above $100) in real-time:
- Bullish/Bearish sentiment indicators
- Position sizes and timestamps
- Wallet behavioral tagging (performance tiers, capitalization tiers)

### 2.5 Top Holders Analysis
View the top 5 holders for each market with:
- Position sizes and percentage ownership
- Performance metrics (PnL, ROI)
- Performance tiers (Top Performer, Massive Winner, etc.)

### 2.6 Price Movement Analytics
Comprehensive price statistics including:
- 24h/7d price changes and percentages
- High/low ranges for each period
- Volume analysis
- Bullish/Bearish trading signals based on momentum, trend, range position, and volume

### 2.7 AI Debate Floor
Multi-agent AI debate system where specialized agents analyze markets from different perspectives:
- Statistics Expert
- Time Decay & Resolution Analyst
- Generalist Expert
- Crypto/Macro Analyst
- Devil's Advocate
- Moderator (final verdict)

### 2.8 User Analytics Dashboard
Search wallet addresses or usernames to view:
- Total P&L alignment
- ROI and win rate
- Top wins and losses

### 2.9 LLM Hub
Configure and manage language model providers for AI features.

### 2.10 POLYGOD Modes
Trading modes with increasing risk levels:
- **Mode 0 (OBSERVE):** Scan only, no tournaments
- **Mode 1 (PAPER):** Scan + paper trading tournaments
- **Mode 2 (LOW):** Scan + Kelly-guarded tournaments
- **Mode 3 (BEAST):** Scan + full live tournaments

---

## 3. Quick Guide - Screen Elements

### 3.1 Header Bar

| Element | Description |
|---------|-------------|
| **POLYGOD Logo** | Main branding, click to return to markets view |
| **Brain Icon** | Shows WebSocket connection status (green = connected, red = disconnected) |
| **MODE Indicator** | Current POLYGOD mode (0-3) with color coding |
| **Paper PnL** | Simulated profit/loss in paper trading mode |
| **Confidence Gauge** | Visual representation of confidence level |
| **SIM Button** | Trigger Monte-Carlo simulation for selected market |
| **View Tabs** | Switch between Markets, User Lab, and LLM Hub |
| **Notification Bell** | Access notification centre with unread alerts |

### 3.2 Ticker Banner
Scrolling ticker showing:
- Whale alerts (when large trades detected)
- Top market prices (Yes percentage)

### 3.3 Sidebar - Market List

| Column | Description |
|--------|-------------|
| **Market Title** | Name of the prediction market |
| **Yes %** | Current probability of "Yes" outcome |
| **Volume** | 24-hour trading volume |
| **Trend Arrow** | Green up = price increased, Red down = price decreased |

### 3.4 Main Content Area - Chart Section

| Element | Description |
|---------|-------------|
| **Market Title** | Selected market name |
| **Current Price** | Yes/No percentages with outcome label |
| **Volume** | 24h trading volume in USD |
| **Timeframe Selector** | Dropdown to select chart timeframe (24H, 7D, 1M, ALL) |
| **Price Chart** | Interactive TradingView chart with OHLC data |

### 3.5 Tab Navigation (News/Whales/Holders/Debate)

| Tab | Icon | Description |
|-----|------|-------------|
| **Related News** | Newspaper | News articles relevant to selected market |
| **Recent Large Orders** | Wallet | Whale trades (>$100) with sentiment indicators |
| **Live Trades** | Activity | Real-time trade feed from WebSocket |
| **Top Holders** | Trophy | Top 5 holders with performance metrics |
| **Price Analysis** | Chart | Price movement statistics and trading signals |
| **Debate Floor** | MessageSquare | AI-powered market analysis debate |

### 3.6 Sidebar - User Lab
- Wallet address search
- Username search
- Total P&L, ROI, win rate display
- Top wins/losses list

### 3.7 Sidebar - LLM Hub
- LLM provider configuration
- API key management
- Model selection

### 3.8 Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + E` | Toggle Edit Mode |
| `Ctrl + ,` | Open Settings Screen |
| `Ctrl + \` | Toggle Hamburger Menu |
| `Cmd+K` / `Ctrl+K` | Open Spotlight Search |
| `Escape` | Close open panels |

### 3.9 Settings Screen
Access via header icon or keyboard shortcut:
- Theme customization
- Notification preferences
- Display preferences
- API configuration

---

## 4. Setup Instructions

### 4.1 Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Python** | 3.12+ | Backend runtime |
| **Node.js** | 18+ | Frontend build |
| **uv** | Latest | Package manager (recommended) |
| **Docker** | Latest | Optional - for containerized deployment |

### 4.2 Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# Required API Keys
NEWS_API_KEY=your_newsapi_key          # Get from https://newsapi.org
GEMINI_API_KEY=your_gemini_key         # For AI Debate features
TAVILY_API_KEY=your_tavily_key         # For AI research

# Optional - Polymarket Trading
POLYMARKET_API_KEY=your_pm_key
POLYMARKET_SECRET=your_pm_secret
POLYMARKET_PASSPHRASE=your_pm_passphrase
POLYMARKET_PRIVATE_KEY=your_hex_key   # For CLOB execution

# Optional - Telegram Notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Optional - Configuration
POLYGOD_MODE=0                         # 0-3 for different risk modes
DATABASE_URL=sqlite+aiosqlite:///./polymarket.db
DEBUG=true
```

### 4.3 Local Development Setup

**Option A: Using start script (Recommended)**
```bash
# Clone the repository
git clone https://github.com/sudo-prog/POLYGOD.git
cd POLYGOD

# Copy environment template
cp .env.example .env

# Start both backend and frontend
./scripts/start.sh
```

**Option B: Manual startup**
```bash
# Terminal 1 - Backend
cd POLYGOD
./scripts/start_backend.sh

# Terminal 2 - Frontend
cd POLYGOD
./scripts/start_frontend.sh
```

**Option C: Docker**
```bash
# Build and start all services
docker compose up --build -d

# Or run in detached mode
docker compose up -d --build
```

### 4.4 Access the Application

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:5173 |
| **Backend API** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |

### 4.5 Verify Installation

1. Open http://localhost:5173 in your browser
2. Verify the market list loads in the sidebar
3. Click on a market to see price chart and data
4. Check the header shows "POLYGOD" with mode indicator

---

## 5. FAQ Section

### General Questions

**Q: What is POLYGOD?**
A: POLYGOD is an AI-powered market intelligence dashboard for Polymarket prediction markets. It provides real-time data visualization, whale tracking, news aggregation, and AI-driven analysis.

**Q: Is POLYGOD free to use?**
A: The dashboard itself is free. However, you may need API keys for certain features:
- NewsAPI key for news feeds (free tier available)
- Gemini/Tavily keys for AI Debate features
- Polymarket keys for trading functionality

**Q: What browsers are supported?**
A: POLYGOD works best on modern browsers (Chrome, Firefox, Safari, Edge). We recommend Chrome for the best experience.

### Feature Questions

**Q: How do I track whale trades?**
A: The "Recent Large Orders" tab shows trades over $100. Each trade shows sentiment (bullish/bearish), size, and timestamp. Whale wallets are tagged with performance and capitalization tiers.

**Q: How does the AI Debate Floor work?**
A: When you select a market and open the Debate Floor, multiple AI agents analyze it from different perspectives (statistics, time decay, macro analysis, etc.) and reach a final verdict. Use the market slug or ID to initiate debate.

**Q: What do the trading signals mean?**
A: Price Analysis tab shows:
- **Bullish:** Momentum and trend indicators suggest upward price movement
- **Bearish:** Momentum and trend suggest downward movement
- **Neutral:** Insufficient data for clear signal

**Q: How do I use the Monte-Carlo simulation?**
A: Click the "SIM" button in the header while a market is selected. It runs 1000 simulations and shows win probability and expected PnL.

**Q: What are POLYGOD modes?**
A: Modes control trading automation levels:
- Mode 0: Observe only (no trading)
- Mode 1: Paper trading (simulated)
- Mode 2: Low risk (Kelly-criterion guarded)
- Mode 3: Full trading (highest risk)

### Technical Questions

**Q: Why isn't data loading?**
A: Check:
1. Backend is running on port 8000
2. API keys are set in .env
3. Database is initialized
4. Check browser console for errors

**Q: How do I restart the application?**
A:
```bash
# Stop all services
pkill -f "uvicorn"  # Backend
pkill -f "npm"      # Frontend

# Restart
./scripts/start.sh
```

**Q: Can I run POLYGOD without Docker?**
A: Yes, see Option A and B in [Setup Instructions](#setup-instructions).

**Q: How do I update POLYGOD?**
```bash
git pull origin main
pip install -r requirements.txt  # Backend
npm install                      # Frontend
```

### Troubleshooting

**Q: WebSocket connection shows red (disconnected)**
A: The WebSocket connection to the backend is not established. Check that the backend is running and accessible at http://localhost:8000.

**Q: News feed is empty**
A: Verify your NEWS_API_KEY is valid and the selected market has related news.

**Q: Chart not loading**
A: Ensure the market has sufficient historical data. Some new markets may not have price history.

**Q: Error: "Module not found"**
A: Reinstall dependencies:
```bash
cd src/backend && pip install -e .
cd src/frontend && npm install
```

---

## 6. Missing & Needed Features

Based on current development status and audit findings, the following features are planned or need implementation:

### 6.1 Critical Bugs (From Audit)

| Bug ID | Severity | Description | Status |
|--------|----------|-------------|--------|
| BUG-07 | HIGH | Dead SQLite connection in polygod_graph.py checkpointer | Needed |
| BUG-09 | HIGH | Debate router double-prefix (404 endpoints) | Needed |
| BUG-08 | HIGH | Wrong Mem0 import class | Needed |
| BUG-06 | HIGH | Dead SQLite connection in snapshot_engine.py | Needed |
| BUG-02 | HIGH | INTERNAL_API_KEY sentinel validation | Needed |

### 6.2 Planned Features

| Feature | Description | Priority |
|---------|-------------|----------|
| **CopyTradeAgent** | Automated trading following top performers | High |
| **RadarScore Module** | Comprehensive whale scoring system | High |
| **Correlation Matrix** | Cross-market correlation for copy-trading | Medium |
| **Orderbook Imbalance Detector** | Real-time orderbook analysis for spoofing/iceberg detection | Medium |
| **OpenTelemetry Integration** | Full observability stack | Low |
| **Alembic Migrations** | Proper database schema versioning | Medium |

### 6.3 User-Requested Features

| Feature | Description |
|---------|-------------|
| **Mobile App** | Native iOS/Android applications |
| **Push Notifications** | Mobile push for whale alerts |
| **Portfolio Tracking** | Personal PnL across all positions |
| **Market Alerts** | Price threshold notifications |
| **Export Data** | CSV/JSON export for analysis |
| **Dark/Light Theme** | Theme toggle option |

### 6.4 Known Limitations

| Limitation | Description |
|-----------|-------------|
| **Rate Limits** | Public API rate limits apply |
| **Historical Data** | Limited to ~30 days for some markets |
| **Latency** | Real-time but not sub-second |
| **Mobile View** | Not optimized for mobile devices |

---

## Appendix: API Reference

### Market Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/markets/top50` | Top 100 markets by 7-day volume |
| `GET /api/markets/{id}` | Single market details |
| `GET /api/markets/{id}/history` | Price history with timeframe |
| `GET /api/markets/{id}/trades` | Recent large trades |
| `GET /api/markets/{id}/holders` | Top holders with PnL/ROI |
| `GET /api/markets/{id}/stats` | Price statistics and signals |
| `GET /api/markets/status` | Data update status |

### Other Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/news/{market_id}` | News for market |
| `POST /api/scan-niches?mode=1` | Scan micro-niches |
| `GET /api/health` | Health check |
| `GET /` | API info |

---

*End of POLYGOD User Manual*
