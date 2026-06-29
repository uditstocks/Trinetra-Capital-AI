# 🔱 Trinetra Capital AI — Glossary & References

This document provides a precise, alphabetised glossary of the domain and technical terms used throughout the Trinetra Capital AI documentation set, followed by a curated reference list of the external systems, libraries, and concepts the project builds upon. Definitions are grounded in the actual source code (`trinetra/`) rather than aspirational descriptions; where the README and the code diverge, the code is authoritative and the discrepancy is noted. Terms are defined as they are *used by Trinetra* — for example, indicator formulas reflect the exact computations in `trinetra/market_data.py`, and order-type semantics reflect the constraints enforced in `trinetra/broker/base.py`.

## Table of Contents

- [Glossary](#glossary)
- [References](#references)
  - [Agent & Orchestration Frameworks](#agent--orchestration-frameworks)
  - [LLM Providers](#llm-providers)
  - [Broker, Auth & Market Data](#broker-auth--market-data)
  - [Numerics, Scraping & Configuration](#numerics-scraping--configuration)
  - [Containerisation](#containerisation)
  - [External URLs Referenced in Code](#external-urls-referenced-in-code)

---

## Glossary

| Term | Definition |
|---|---|
| **Access token** | A short-lived (typically daily) credential Trinetra obtains from Groww to authorise API calls. Generated via the TOTP or approval flow in `trinetra/broker/groww_client.py` and cached to `.groww_token_cache.json` keyed by date and auth method (file permissions set to `600` on a best-effort basis), so the system re-authenticates at most once per day. A single transparent re-auth retry occurs in `GrowwBroker._call()` on a `401`/auth error. |
| **ATR (Average True Range, ATR-14)** | A volatility indicator. Trinetra computes True Range as the per-bar maximum of (high − low), |high − prev close|, |low − prev close|, then smooths it with an exponentially weighted mean (`com=13`, equivalent to a 14-period Wilder average) over 90 days of daily data. ATR drives the derived risk levels: `stop_loss = price − 1.5·ATR`, `target_1 = price + 2.0·ATR`, `target_2 = price + 3.5·ATR`. |
| **Bollinger %B** | A normalised position of price within its Bollinger Bands. Computed from a 20-period SMA with ±2σ bands as `(close − lower_band) / (band_width)`. Values below 0.2 contribute `+10` to the composite score; above 0.8, `−10`. |
| **Broker layer** | The abstraction (`trinetra/broker/base.py`) that lets the agents trade without knowing whether fills are simulated or real. Defines the abstract `Broker` class, normalised data types (`OrderRequest`, `OrderResult`, `Holding`, `Position`, `Funds`), and the `guard_order()` safety check. `get_broker()` returns a `PaperBroker` or `GrowwBroker` singleton based on the configured mode. |
| **BSE (Bombay Stock Exchange)** | One of the two Indian equity exchanges Trinetra supports. Symbols on BSE map to the `.BO` yfinance suffix and exchange tokens prefixed `BSE_`. |
| **CASH segment** | The equity cash (delivery/intraday) market segment — the only segment Trinetra supports in v1. The instrument master is filtered to `segment=CASH`, and all broker calls pass the `CASH` segment constant. F&O and commodity segments are out of scope for this version. |
| **Checkpointer / thread** | LangGraph's mechanism for persisting conversation state. Trinetra compiles its supervisor graph with an `InMemorySaver` checkpointer. A *thread* (identified by a `thread_id`) scopes a conversation's saved state. Note: the CLI assigns a **fresh `uuid4` thread_id per turn**, so there is no long-term cross-turn memory yet (persistent `PostgresSaver` storage is on the roadmap). |
| **CNC (Cash and Carry)** | A Groww product type for **delivery** trades — shares are held in the demat account. Trinetra's default product (`GROWW_DEFAULT_PRODUCT=CNC`). |
| **Composite score** | A 0–100 technical+sentiment score computed in `technical_snapshot()`. Starts at 50, then: RSI bands (`+20` if <30, `+10` if <40, `−20` if >70, `−10` if >60); MACD histogram (`+15` if positive, else `−15`); Bollinger %B (`+10` if <0.2, `−10` if >0.8); plus `round(avg_sentiment·15)`; clamped to 0–100. Maps to a signal: **BUY** if ≥65, **SELL** if ≤35, else **HOLD**; confidence is *high* at ≥80 or ≤20, else *moderate*. |
| **Confidence** | A qualitative label (`high`/`moderate`) attached to the composite signal, indicating how decisive the score is (extreme scores ≥80 or ≤20 yield high confidence). |
| **Equity** | Shares of publicly listed Indian companies traded on NSE/BSE — the asset class Trinetra trades in v1. |
| **Exchange token** | A composite identifier of the form `EXCHANGE_SYMBOL` (e.g. `NSE_RELIANCE`) used as the key for Groww LTP lookups and the short-lived price cache. Produced by `Instrument.exchange_token` in `trinetra/symbols.py`. Contrast with **trading symbol**. |
| **HITL (Human-in-the-Loop)** | A safety pattern requiring explicit human approval before an irreversible action. Trinetra wraps the trading agent in a `HumanInTheLoopMiddleware` that interrupts on every `place_order`, `cancel_order`, and `modify_order`. The CLI surfaces an order summary and prompts yes/no; approval resumes the graph via `Command(resume=...)`. |
| **Instrument master** | The authoritative catalogue of tradable Groww instruments (`trinetra/instruments.py`). Downloaded from a public CSV (no auth), cached to `.groww_instruments.csv`, refreshed daily, filtered to `segment=CASH` on NSE/BSE. Provides `search()` ranking and `resolve()` so user-supplied names/tickers map to real, tradable symbols (e.g. `INFOSYS.NS → INFY`) before any order reaches the broker. |
| **Limit order** | An order to buy/sell at a specified price or better. Requires a positive `price`; validated in `OrderRequest.normalised()`. Supported in both paper and live modes. |
| **LTP (Last Traded Price)** | The most recent traded price of an instrument. `try_ltp()` returns a cheap LTP (Groww-first, yfinance fallback), and `ltp_many()` batches lookups (Groww caps 50 symbols/call). A 10-second TTL cache (`_LTP_TTL`) deduplicates repeated lookups within a turn while keeping prices effectively live. |
| **MACD (Moving Average Convergence Divergence)** | A momentum indicator. Trinetra uses the MACD *histogram*: `(EMA12 − EMA26) − signal`, where the signal is `EMA9` of the MACD line. A positive histogram is treated as bullish (`+15` to the composite); negative as bearish (`−15`). |
| **Market order** | An order to buy/sell immediately at the prevailing market price. For market (and SL_M) orders Trinetra fetches a reference LTP to estimate value for the safety cap. Filled instantly by the paper broker. |
| **MIS (Margin Intraday Square-off)** | A Groww product type for **intraday** trades, squared off the same day. Selectable via `GROWW_DEFAULT_PRODUCT=MIS`. |
| **NSE (National Stock Exchange)** | India's largest equity exchange and Trinetra's default exchange (`GROWW_DEFAULT_EXCHANGE=NSE`). Symbols map to the `.NS` yfinance suffix and `NSE_` exchange tokens. |
| **OHLC** | Open, High, Low, Close — the four daily price points returned by `get_live_quote()` (from Groww's `ohlc` block, with `close` interpreted as previous close) and used to build daily history for indicators. |
| **OrderRequest** | The normalised order dataclass in `base.py`. `normalised()` validates and canonicalises symbol, exchange, transaction type, order type, product, quantity, and price/trigger constraints, raising `BrokerError` on bad input. `estimated_value()` computes a best-effort notional for the cap check. |
| **Paper vs live trading** | The two operating modes. **Paper** (the default, `GROWW_TRADING_MODE=paper`) routes to `PaperBroker`, which simulates fills and persists a trade log to `portfolio.json`. **Live** (`=live`) routes to `GrowwBroker` and places **real-money** orders against the user's Groww account, gated behind an explicit `I UNDERSTAND` confirmation. Market data is real and live in both modes. |
| **Per-order cap** | A hard rupee ceiling (`settings.max_order_value`, default ₹100,000, env `GROWW_MAX_ORDER_VALUE`) enforced by `Broker.guard_order()` for **both** paper and live orders before anything is sent. Orders exceeding the cap raise `BrokerError`. |
| **RSI (Relative Strength Index, RSI-14)** | A momentum oscillator (0–100). Computed with Wilder smoothing (`ewm(com=13)`) of average gains/losses over 90 days of daily closes. Labelled *oversold* (<30) or *overbought* (>70); feeds the composite score via banded contributions. |
| **Sentiment polarity** | A −1…+1 score from TextBlob applied to up to 10 scraped Yahoo Finance headlines. The average polarity is labelled *bullish* (>0.15), *bearish* (<−0.15), or *neutral*, and contributes `round(avg·15)` to the composite score. This is best-effort headline scraping, not a curated news feed. |
| **SL (Stop-Loss limit)** | A stop-loss order with both a `trigger_price` and a limit `price`; activates a limit order once the trigger is hit. Rejected by the paper broker (it cannot monitor a live trigger). |
| **SL_M (Stop-Loss market)** | A stop-loss order with only a `trigger_price`; activates a market order once the trigger is hit. Also rejected in paper mode — stop-loss orders are **not simulated** in paper trading. |
| **Specialist agent** | One of the three worker agents (`research_agent`, `sentiment_agent`, `trading_agent`), each built with `create_agent` and equipped with a focused tool set. The supervisor routes a request to exactly one specialist. |
| **Supervisor agent** | The router built via `langgraph-supervisor`'s `create_supervisor`. It classifies each request by intent (execution → trading, advice → sentiment, information → research), delegates to exactly one specialist, and relays the reply verbatim. It never calls tools itself. |
| **Trading symbol** | The bare Groww ticker (e.g. `RELIANCE`, `INFY`) without exchange decoration. Distinct from the **exchange token** (`NSE_RELIANCE`) and from the yfinance symbol (`RELIANCE.NS`). Resolution to a canonical trading symbol happens via the instrument master before order placement. |
| **Trigger price** | The threshold that activates a stop-loss order. Required (and must be positive) for SL and SL_M order types, validated in `OrderRequest.normalised()`. |
| **TOTP (Time-based One-Time Password)** | An auth flow (RFC 6238) in which `pyotp` derives a rotating code from `GROWW_TOTP_SECRET` to mint a daily Groww access token. The recommended flow ("flow A"); the alternative "approval flow" uses `GROWW_API_KEY` + `GROWW_API_SECRET`. |
| **UCC (Unique Client Code)** | The broker-assigned unique identifier for a client account, a SEBI requirement for Indian market participants. Relevant context for any real-money Groww account Trinetra trades on; Trinetra itself authenticates via API key/TOTP rather than handling the UCC directly. |

---

## References

The following external systems, libraries, and concepts underpin Trinetra Capital AI. Versions and constraints reflect `requirements.txt`; usage reflects the actual imports in the codebase.

### Agent & Orchestration Frameworks

| Reference | Role in Trinetra |
|---|---|
| **LangChain** (`langchain`, `langchain-core`) | Provides the `create_agent` builder, tool abstractions (`@tool`), chat-model interfaces, and the `HumanInTheLoopMiddleware` used to gate risky trading tools. The agents' only surface to the system is the LangChain tool layer in `trinetra/tools.py`. |
| **LangGraph** (`langgraph`) | The stateful graph runtime that executes the multi-agent workflow. Supplies the `InMemorySaver` checkpointer, the `__interrupt__` mechanism that HITL builds on, `Command(resume=...)` for resuming after approval, and `GraphRecursionError` (handled gracefully in the CLI). |
| **langgraph-supervisor** (`langgraph-supervisor`) | Implements the hierarchical supervisor pattern via `create_supervisor(...)`. Trinetra configures it with `output_mode="last_message"`, `add_handoff_messages=False`, and `add_handoff_back_messages=False` so the supervisor relays exactly one specialist's final answer. |

### LLM Providers

The LLM layer is **pluggable and provider-configurable**. The code default for both the agent and supervisor models is `meta/llama-3.3-70b-instruct` (`trinetra/config.py`), not the NVIDIA `nemotron-3-super-120b` model named in the README tech table.

| Reference | Role in Trinetra |
|---|---|
| **NVIDIA NIM endpoints** (`langchain-nvidia-ai-endpoints`, `ChatNVIDIA`) | Default provider for the worker/specialist agents, authenticated with `NVIDIA_API_KEY`. NIM (NVIDIA Inference Microservices) exposes hosted models behind an OpenAI-style API. |
| **Groq** (`langchain-groq`, `ChatGroq`) | Default provider for the *supervisor*, chosen for low-latency routing (`use_groq_supervisor` default `True`, `GROQ_API_KEY`). Falls back to the worker LLM if Groq is unavailable. |
| **OpenRouter** (`ChatOpenAI`-compatible) | Optional override that powers **both** supervisor and agents when `OPENROUTER_API_KEY` is set and `TRINETRA_USE_OPENROUTER` is true (default true). Default OpenRouter model: `openai/gpt-4o-mini`. Routes via a configurable `OPENROUTER_BASE_URL`. |

### Broker, Auth & Market Data

| Reference | Role in Trinetra |
|---|---|
| **Groww Trading API + `growwapi` SDK** (`growwapi>=1.5.0`) | The real broker. `GrowwBroker` wraps the `GrowwAPI` client to place/cancel/modify orders and fetch holdings, positions, funds, order status, and history, plus live quotes/LTP/OHLC. Scope is the equity CASH segment on NSE/BSE in v1. |
| **pyotp** (`pyotp`) | Generates time-based one-time passwords from `GROWW_TOTP_SECRET` to mint the daily Groww access token in the TOTP auth flow. |
| **yfinance** (`yfinance`) | Fallback market-data source so research and sentiment work even before a Groww account is connected. Supplies quote fallback (`_yf_quote`), 90-day daily history for indicators, fundamentals via `.info` (company/sector/PE/market-cap/52-week), and `Search` as a last-resort symbol lookup. |

### Numerics, Scraping & Configuration

| Reference | Role in Trinetra |
|---|---|
| **NumPy** (`numpy`) | Numerical helpers — e.g. averaging sentiment polarity scores (`np.mean`) in `technical_snapshot()`. |
| **pandas** (`pandas`) | Time-series engine for the technical indicators: rolling/EWM windows for RSI, MACD, Bollinger %B, and ATR over the daily price history. |
| **requests** (`requests`) | HTTP client used to fetch Yahoo Finance news pages for headline sentiment scraping. |
| **BeautifulSoup** (`beautifulsoup4`) | HTML parser that extracts `<h3>` headline text from the scraped Yahoo Finance news pages (best-effort, up to 10 headlines). |
| **TextBlob** (`textblob`) | Lexicon-based NLP that scores the polarity of each scraped headline, feeding the sentiment component of the composite score. |
| **python-dotenv** (`python-dotenv`) | Loads configuration from `.env` into the frozen `Settings` dataclass (`trinetra/config.py`), the single source of truth for credentials, mode, caps, and model selection. |

### Containerisation

| Reference | Role in Trinetra |
|---|---|
| **Docker / Docker Compose** | Packages the application on a `python:3.12-slim` base image. `docker-compose` injects `.env` and volume-mounts `portfolio.json` so the paper trade log persists across container runs. |

### External URLs Referenced in Code

| URL | Purpose |
|---|---|
| `https://groww.in/trade-api/docs` | Official Groww Trading API documentation (credential generation, endpoints), referenced in the onboarding flow. |
| `https://growwapi-assets.groww.in/instruments/instrument.csv` | The public, no-auth instrument-master CSV downloaded by `trinetra/instruments.py`, cached locally and refreshed daily. |

---

[← Roadmap & Future Work](12-roadmap-and-future-work.md)  |  [↑ Documentation Index](README.md)
