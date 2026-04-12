# 🔱 Trinetra Capital AI
### *Multi-Agents. One Market. Zero Missed Moves.*

> An autonomous, multi-agent AI trading system built with LangGraph, LangChain, and NVIDIA NIM — designed for real-time stock research, intelligent order execution, and human-in-the-loop safety controls.

---

## ⚡ What is Trinetra Capital AI?

Trinetra Capital AI is a **production-grade agentic trading system** that orchestrates multiple specialized AI agents under a central supervisor. It fetches live market data, performs stock research, and executes buy/sell orders — all while keeping a human in control of every critical decision.

Built for both **Indian markets (NSE/BSE)** and **US markets (NASDAQ/NYSE)**, with automatic currency detection and persistent portfolio tracking.

---

## 🏗️ System Architecture

```
╔══════════════════════════════════════════════════════════════════════╗
║                        USER INPUT (CLI)                              ║
╚══════════════════════════════════╦═══════════════════════════════════╝
                                   ║
                                   ▼
╔══════════════════════════════════════════════════════════════════════╗
║               SUPERVISOR AGENT — Groq LLaMA 3.3-70B                 ║
║                                                                      ║
║   • Interprets user intent        • Routes to correct agent          ║
║   • Coordinates multi-agent flow  • Synthesizes final response       ║
║   • Maintains conversation state  • LangGraph checkpointing          ║
╚═════════════════╦════════════════════════════╦════════════════════════╝
                  ║                            ║
          transfer_to_research         transfer_to_trading
                  ║                            ║
                  ▼                            ▼
╔═════════════════════════╗      ╔══════════════════════════════════════╗
║     RESEARCH AGENT      ║      ║          TRADING AGENT              ║
║     NVIDIA NIM          ║      ║          NVIDIA NIM                 ║
║  nemotron-3-super-120b  ║      ║       nemotron-3-super-120b         ║
║                         ║      ║                                      ║
║  Tools:                 ║      ║  Tools:                             ║
║  ├─ lookup_stocks       ║      ║  ├─ place_order ──→ [HITL GATE]    ║
║  │   ├─ NSE (.NS)       ║      ║  └─ view_portfolio                  ║
║  │   ├─ BSE (.BO)       ║      ║                                      ║
║  │   └─ US (NASDAQ)     ║      ║  Auto-detects:                      ║
║  └─ fetch_stock_data    ║      ║  ├─ Currency (INR / USD)            ║
║      ├─ Live price      ║      ║  └─ Exchange type                   ║
║      ├─ 52W High/Low    ║      ║                                      ║
║      ├─ P/E Ratio       ║      ╚══════════════╦═══════════════════════╝
║      ├─ Market Cap      ║                     ║
║      ├─ Sector          ║                     ▼
║      └─ 5D Range        ║      ╔══════════════════════════════════════╗
╚═════════════════════════╝      ║       HUMAN APPROVAL GATE           ║
                                 ║   HumanInTheLoopMiddleware           ║
                                 ║                                      ║
                                 ║   Shows: Symbol | Shares | Price     ║
                                 ║   Action: [APPROVE] or [REJECT]      ║
                                 ║   Powered by LangGraph interrupt()   ║
                                 ╚══════════════╦═══════════════════════╝
                                                ║
                                                ▼
                                 ╔══════════════════════════════════════╗
                                 ║         portfolio.json               ║
                                 ║      Persistent Trade Log            ║
                                 ║                                      ║
                                 ║  { symbol, action, shares,           ║
                                 ║    price, total, currency,           ║
                                 ║    timestamp }                       ║
                                 ╚══════════════════════════════════════╝
                                                ║
                                                ▼
                                 ╔══════════════════════════════════════╗
                                 ║         LANGSMITH                    ║
                                 ║      Full Observability Layer        ║
                                 ║                                      ║
                                 ║  • Agent traces    • Token usage     ║
                                 ║  • Tool I/O        • Latency P50/P99 ║
                                 ╚══════════════════════════════════════╝
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Agent Framework** | LangGraph 1.0, LangChain 1.0 |
| **Multi-Agent** | `langgraph-supervisor` — Hierarchical supervisor pattern |
| **LLM (Agents)** | NVIDIA NIM — `nemotron-3-super-120b` |
| **LLM (Supervisor)** | Groq — `llama-3.3-70b-versatile` |
| **Market Data** | `yfinance` — Real-time NSE/BSE/US prices |
| **HITL** | `HumanInTheLoopMiddleware` — Interrupt-based approval |
| **Memory** | `InMemorySaver` — LangGraph checkpointing |
| **Observability** | LangSmith — Full agent trace & token analytics |
| **Containerization** | Docker + Docker Compose |
| **Portfolio Storage** | JSON — Persistent trade logging |

---

## ✅ Current Features

### 🤖 Multi-Agent Architecture
- **Supervisor Agent** — Routes tasks between specialized agents using Groq LLaMA 3.3
- **Research Agent** — Handles all stock lookup and market data fetching
- **Trading Agent** — Executes orders with built-in human approval gate
- Hierarchical coordination via `langgraph-supervisor` library

### 🛡️ Human-in-the-Loop (HITL)
- Every `place_order` call is intercepted before execution
- Full order details shown for review (symbol, shares, price, total)
- Approve / Reject decision via CLI
- Powered by LangChain's `HumanInTheLoopMiddleware`

### 📊 Smart Stock Research
- Yahoo Finance powered symbol lookup (no API key required)
- Supports **Indian stocks** (NSE `.NS` / BSE `.BO`) and **US stocks**
- Auto-detects exchange from query ("TCS NSE", "Reliance BSE")
- Fetches: latest price, 52W high/low, P/E ratio, market cap, sector, 5D range

### 💱 Currency Intelligence
- Auto-detects currency from stock symbol
- Indian stocks → `₹ INR`
- US stocks → `$ USD`
- No manual input required

### 📁 Persistent Portfolio Tracker
- Every filled order logged to `portfolio.json`
- Persists across sessions and container restarts
- Agent can query portfolio anytime via `view_portfolio` tool
- Tracks: symbol, action, shares, price, total, currency, timestamp

### 🔍 LangSmith Observability
- Full execution trace for every agent run
- Token usage analytics per tool call
- Latency monitoring (P50/P99)
- Debug individual tool inputs/outputs

### 🐳 Docker Ready
- Single command setup — no Python install needed
- `docker-compose build && docker-compose run trading-agent`
- Environment variables injected via `.env`
- Portfolio data persisted via Docker volumes

---

## 🚀 Getting Started

### Prerequisites
- Docker & Docker Compose
- API Keys (see `.env.example`)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/uditstocks/Advance_LangGraph.git
cd Advance_LangGraph

# 2. Setup environment variables
cp .env.example .env
# Edit .env with your API keys

# 3. Build Docker image
docker-compose build

# 4. Run the agent
docker-compose run trading-agent
```

### Without Docker

```bash
pip install -r requirements.txt
python Human_in_Loop/prebuilt_HITL.py
```

---

## 🔑 Environment Variables

Create a `.env` file in the root directory:

```env
# NVIDIA NIM API
NVIDIA_API_KEY=your_nvidia_api_key

# Groq API (Supervisor LLM)
GROQ_API_KEY=your_groq_api_key

# LangSmith Observability
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=trinetra-capital-ai
```

---

## 💬 Example Interactions

```
# ── Indian Market ──────────────────────────────────────────
> buy 5 shares of Reliance
  → Supervisor routes to Research Agent
  → Looks up RELIANCE.NS on Yahoo Finance
  → Fetches live price ₹1,350.20, P/E 21.98, Market Cap ₹18.27T
  → Routes to Trading Agent
  → HITL Gate: "Approve buy 5 × RELIANCE.NS @ ₹1,350.20? (yes/no)"
  → Order fills: Total ₹6,751.00 INR — logged to portfolio

# ── US Market ──────────────────────────────────────────────
> buy 3 shares of Apple with a budget of $1000
  → Research Agent fetches AAPL: $260.48, P/E 33.01, 52W high $288.62
  → Agent computes: floor(1000 / 260.48) = 3 shares
  → HITL Gate: "Approve buy 3 × AAPL @ $260.48? (yes/no)"
  → Order fills: Total $781.44 USD — logged to portfolio

# ── Exchange Specific ──────────────────────────────────────
> buy 10 shares of TCS NSE
  → Research Agent forces .NS suffix lookup → TCS.NS
  → Fetches live NSE price, sector, market cap
  → Routes to Trading Agent with verified data

# ── Portfolio Query ────────────────────────────────────────
> show my complete portfolio
  → Trading Agent calls view_portfolio tool
  → Reads portfolio.json → Returns full trade history
  → Agent formats: Holdings table with INR/USD split

# ── Multi-turn Memory ──────────────────────────────────────
> what did I buy today?
  → Supervisor recalls conversation context via checkpointing
  → Returns today's trades from session memory
```

---

## 📁 Project Structure

```
Advance_LangGraph/
├── Human_in_Loop/
│   └── prebuilt_HITL.py      # Main agent system
├── Dockerfile                 # Container definition
├── docker-compose.yml         # Service orchestration
├── requirements.txt           # Python dependencies
├── .env.example               # Environment template
├── .dockerignore              # Docker build exclusions
├── .gitignore                 # Git exclusions
└── portfolio.json             # Generated at runtime
```

---

## 🔭 Roadmap — Coming Soon

| Feature | Description | Status |
|---------|-------------|--------|
| **PostgreSQL Persistent Memory** | Replace `InMemorySaver` with `PostgresSaver` — production-grade persistent memory that survives restarts | 🔄 Planned |
| **RAG — Trade Intelligence** | FAISS + NVIDIA embeddings vector store — agent queries past trades, market notes, and historical decisions via semantic search | 🔄 Planned |
| **News Sentiment Analysis** | Real-time news fetch before trade execution — NLP sentiment scoring, auto-warn on bearish signals | 🔄 Planned |
| **Rich Terminal Dashboard** | `rich` library powered UI — live panels for agent reasoning, tool calls, portfolio summary, and approval prompts | 🔄 Planned |
| **Async Execution** | Full `async/await` with `ainvoke` — non-blocking multi-agent execution for faster response times | 🔄 Planned |
| **Portfolio P&L Engine** | Real-time profit/loss calculation — compares buy price vs current market price across all holdings | 🔄 Planned |
| **Options Chain Analysis** | Fetch and analyze options data — PCR, OI buildup, IV crush detection for smarter trade decisions | 🔄 Planned |
| **Real Broker API Integration** | Connect to **Zerodha Kite**, **Upstox**, or **Groww** APIs — execute real trades, fetch live orderbook, manage positions | 🔄 Planned |
| **Cloud Deployment** | Deploy on AWS/GCP/Azure — always-on trading agent with webhook triggers, scheduled market scans | 🔄 Planned |
| **Multi-Asset Support** | Extend beyond equities — Mutual Funds, ETFs, Crypto, Commodities under one unified agent system | 🔄 Planned |

---

## 🧠 Key LangGraph Concepts Used

- **StateGraph** — Graph-based agent execution flow
- **Supervisor Pattern** — Central orchestrator with specialized worker agents
- **HumanInTheLoop Interrupts** — Dynamic pause/resume via `interrupt()` function
- **Checkpointing** — `InMemorySaver` for conversation state persistence
- **Tool Calling** — Structured tool definitions with `@tool` decorator
- **Handoff Tools** — Agent-to-agent communication via `transfer_to_*` tools
- **Middleware** — `HumanInTheLoopMiddleware` for pre-execution approval gates

---

## 📊 Performance (LangSmith Metrics)

| Metric | Value |
|--------|-------|
| Token usage (optimized) | ~2K–6K per run |
| Token usage (before optimization) | ~16K–60K per run |
| Token reduction | **~10x** |
| Avg latency | ~30–45s (multi-agent) |

---

## 🔱 About

Built with 🔱 by **Udit** — AI Engineering Student, India

Passionate about the full Agentic AI stack — **LangChain**, **LangGraph**, **CrewAI**, **RAG Pipelines**, **Vector Databases (FAISS, pgvector, Chroma)**, **Multi-Agent Orchestration**, **NVIDIA NIM**, **Groq**, **MCP (Model Context Protocol)**, **Tool Calling**, **Prompt Engineering**, **Human-in-the-Loop Systems**, **Embedding Models**, **Semantic Search**, and building production-grade Generative AI systems that solve real-world financial problems at scale.

> *"Har decision mein teen nazar — research ki, trading ki, aur insaan ki."*

---

## ⚠️ Disclaimer

This is a **paper trading simulation** for educational purposes only. No real money is involved. Always consult a SEBI-registered financial advisor before making actual investment decisions.
