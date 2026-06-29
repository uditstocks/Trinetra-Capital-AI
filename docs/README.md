# 🔱 Trinetra Capital AI — Documentation

> **Multi-Agents. One Market. Zero Missed Moves.**
> Official technical & research documentation for **Trinetra Capital AI** — an autonomous, multi-agent AI trading system for Indian equities (NSE/BSE), built on LangGraph and wired to the **Groww Trading API**, with human-in-the-loop safety on every order.

This folder is the canonical documentation set for the project. It is written to a **research-grade** standard for academic and competition review, while remaining a practical reference for developers and operators. Every technical claim is grounded in the tracked source code under [`trinetra/`](../trinetra/).

---

## 📖 How to read this documentation

The documentation is organised as a numbered set of chapters that build on one another, plus a standalone research paper and supporting guides. Each chapter is self-contained and cross-links to the others, with previous/next navigation at the foot of every page.

| Audience | Suggested reading path |
|---|---|
| **Competition / research evaluators** | [Research Paper](research-paper/RESEARCH_PAPER.md) → [01 Introduction](01-introduction.md) → [02 Architecture](02-system-architecture.md) → [05 Quantitative Analytics](05-market-data-and-quant-analytics.md) → [06 Safety & Security](06-safety-risk-and-security.md) |
| **Developers / contributors** | [02 Architecture](02-system-architecture.md) → [03 Multi-Agent](03-multi-agent-system.md) → [04 Broker Layer](04-execution-and-broker-layer.md) → [10 API Reference](10-api-reference.md) → [../CONTRIBUTING.md](../CONTRIBUTING.md) |
| **Operators / users** | [08 Installation & Deployment](08-installation-and-deployment.md) → [07 Configuration](07-configuration-reference.md) → [09 Usage Guide](09-usage-guide.md) → [06 Safety & Security](06-safety-risk-and-security.md) |

---

## 📚 Documentation map

### Core chapters

| # | Document | What it covers |
|--:|----------|----------------|
| 01 | [Introduction & Project Overview](01-introduction.md) | Problem statement, motivation, the "three-eyed" concept, objectives, contributions, scope. |
| 02 | [System Architecture](02-system-architecture.md) | Layered architecture, component map, request lifecycle, design principles. |
| 03 | [Multi-Agent Orchestration](03-multi-agent-system.md) | Supervisor–specialist design, intent routing, HITL middleware, LLM provider strategy, state. |
| 04 | [Execution & Broker Layer](04-execution-and-broker-layer.md) | Broker abstraction, order lifecycle, paper vs live brokers, Groww session management. |
| 05 | [Market Data & Quantitative Analytics](05-market-data-and-quant-analytics.md) | Data sourcing, symbol resolution, technical indicators, sentiment, composite scoring. |
| 06 | [Safety, Risk Management & Security](06-safety-risk-and-security.md) | Defence-in-depth controls, credential & token security, regulatory & ethical considerations. |
| 07 | [Configuration Reference](07-configuration-reference.md) | Every environment variable, the `Settings` model, modes, auth flows, generated files. |
| 08 | [Installation & Deployment](08-installation-and-deployment.md) | Setup, Groww onboarding, first run, Docker, troubleshooting. |
| 09 | [Usage Guide & Interaction Catalogue](09-usage-guide.md) | CLI walkthrough, interaction patterns by intent, the approval experience. |
| 10 | [API & Module Reference](10-api-reference.md) | Module-by-module reference of the `trinetra` package public surface. |
| 11 | [Testing & Validation](11-testing-and-validation.md) | Validation philosophy, manual test matrix, recommended unit tests. |
| 12 | [Roadmap & Future Work](12-roadmap-and-future-work.md) | Current status, honest limitations, planned features, research directions. |
| 13 | [Glossary & References](13-glossary-and-references.md) | Domain & technical terminology, external systems and libraries relied upon. |

### Research & supporting documents

| Document | Purpose |
|----------|---------|
| [📄 Research Paper / Whitepaper](research-paper/RESEARCH_PAPER.md) | Formal, citable academic write-up of the system for competition submission. |
| [🤝 Contributing & Documentation Guide](../CONTRIBUTING.md) | How to contribute code and keep this documentation current. |
| [🗒️ Changelog](../CHANGELOG.md) | Versioned record of notable changes. |
| [📘 Project README](../README.md) | Quick-start landing page for the repository. |

---

## 🧭 At a glance

| | |
|---|---|
| **Project** | Trinetra Capital AI |
| **Version** | 1.0.0 |
| **Domain** | Autonomous multi-agent trading for Indian equities (NSE / BSE) |
| **Core stack** | LangGraph · LangChain · `langgraph-supervisor` · NVIDIA NIM / Groq / OpenRouter · Groww Trading API · yfinance |
| **Default mode** | **Paper** (simulated) — live real-money trading is explicit opt-in |
| **Safety** | Per-order value cap · human-in-the-loop approval · live confirmation gate · authoritative symbol resolution |
| **Entrypoint** | `python main.py` |

---

## ⚠️ Disclaimer

Trinetra Capital AI can place **real orders with real money** when `GROWW_TRADING_MODE=live`. It is provided for educational and research use, **without warranty**. Automated trading carries significant financial risk; you are solely responsible for every order it places. Start in paper mode, keep the per-order cap conservative, review every approval prompt, and consult a SEBI-registered advisor before trading. **This is not investment advice.** See [06 — Safety, Risk Management & Security](06-safety-risk-and-security.md) for the full risk model.
