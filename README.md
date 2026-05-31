---
title: Aurum AI Finance Assistant
emoji: 💰
colorFrom: yellow
colorTo: green
sdk: docker
pinned: false
app_port: 7860
---

# ⚜️ Aurum — AI Finance Assistant

> Democratizing financial literacy through intelligent conversational AI

Aurum is a production-ready multi-agent financial education assistant powered by LangGraph, FastAPI, and React. Six specialized AI agents collaborate to answer questions about investing, your portfolio, live market data, financial goals, news, and tax concepts.

## Architecture

```
React SPA → FastAPI (WebSocket + REST) → LangGraph Supervisor
                                              ├── QA Agent (RAG)
                                              ├── Portfolio Agent
                                              ├── Market Agent (yfinance)
                                              ├── Goals Agent (Monte Carlo)
                                              ├── News Agent (Google News)
                                              └── Tax Agent (RAG)
                                         ↓
                          ChromaDB · Redis · PostgreSQL
```

## Quick Start (Local)

```bash
# 1. Clone and set up environment
git clone <repo>
cd aurum
cp .env.example .env
# Edit .env: set LLM_PROVIDER, LLM_MODEL, and the matching API key

# 2. Start all services
docker compose up -d

# 3. Seed the knowledge base
docker compose --profile seed up rag-ingest

# 4. Open the app
open http://localhost:5173
```

## LLM Configuration

Set `LLM_PROVIDER` and `LLM_MODEL` in `.env`:

| Provider | `LLM_PROVIDER` | `LLM_MODEL` | Key Required |
|---|---|---|---|
| Anthropic | `anthropic` | `claude-opus-4-7` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai` | `gpt-4o` | `OPENAI_API_KEY` |
| Google | `google` | `gemini-2.0-flash` | `GOOGLE_API_KEY` |
| AWS Bedrock | `bedrock` | `anthropic.claude-...` | AWS keys |

## Local Development (without Docker)

```bash
# Backend
uv pip install -e ".[anthropic,dev]"
uvicorn src.api.main:app --reload   # port 8000

# Frontend
cd ui && npm install && npm run dev  # port 5173

# Seed RAG
python -m src.rag.ingest --seed-dir src/rag/seed
```

## Hugging Face Spaces Deploy

```bash
# Build single-container image
docker build -f Dockerfile.hf -t aurum-hf .
docker run -p 7860:7860 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e SECRET_KEY=your-secret \
  aurum-hf
open http://localhost:7860

# Deploy to HF Spaces
huggingface-cli login
huggingface-cli repo create aurum --type space --space-sdk docker
git remote add hf https://huggingface.co/spaces/{username}/aurum
git push hf main
# Set ANTHROPIC_API_KEY and SECRET_KEY in HF Space secrets
```

## API Reference

- `POST /api/auth/register` — Create account
- `POST /api/auth/login` — Get JWT
- `WS  /api/chat/ws?conversation_id=...&token=...` — Streaming chat
- `GET /api/market/quote/{symbol}` — Live stock quote
- `GET /api/market/indices` — Major indices
- `GET /api/portfolio` — User portfolios
- `GET /api/goals` — Financial goals
- `POST /api/goals/{id}/projection` — Monte Carlo projection
- `GET /api/news?query=...` — Financial news
- `GET /api/settings/adapters/health` — Data source status
- Full Swagger docs: `http://localhost:8000/api/docs`

## Agents

| Agent | Domain | Data Sources |
|---|---|---|
| **QA** | Financial education | ChromaDB RAG |
| **Portfolio** | Holdings & performance | DB + live prices |
| **Market** | Real-time market data | yfinance (Google Finance compatible) |
| **Goals** | Goal planning & projection | Monte Carlo simulation |
| **News** | Financial news | Google News RSS |
| **Tax** | Tax education | ChromaDB RAG |

## MCP Server

Aurum exposes 8 finance tools via the [Model Context Protocol](mcp_server/README.md), enabling Claude Desktop to query live market data, analyze portfolios, and run Monte Carlo projections directly from a conversation.

**Local (Claude Desktop stdio):**
```bash
pip install -e ".[mcp]"
python3 -m mcp_server.server
```
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "aurum-finance": {
      "command": "python3",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/Aurum",
      "env": { "USE_IN_MEMORY_CACHE": "true" }
    }
  }
}
```

**Remote (Hugging Face Spaces or any HTTP host):**

The MCP server mounts automatically at `/mcp` when `MCP_ENABLED=true` (set in `Dockerfile.hf` and `docker-compose.yml`). Claude Desktop connects via `mcp-remote`:
```json
{
  "mcpServers": {
    "aurum-finance": {
      "command": "npx",
      "args": ["mcp-remote", "https://YOUR_USERNAME-aurum.hf.space/mcp",
               "--header", "X-API-Key:YOUR_MCP_API_KEY"]
    }
  }
}
```
Set `MCP_API_KEY` in HF Space secrets to protect the public endpoint. See [`mcp_server/README.md`](mcp_server/README.md) for full setup.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, LangGraph, LangChain
- **LLM**: Configurable (Anthropic Claude, OpenAI GPT, Google Gemini, AWS Bedrock)
- **Market Data**: yfinance (primary), Alpha Vantage (fallback, pluggable)
- **RAG**: ChromaDB, sentence-transformers (`all-MiniLM-L6-v2`)
- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Recharts
- **Infrastructure**: PostgreSQL, Redis, Docker

## Usage Examples

Start a conversation in the chat interface. Aurum automatically routes your message to the right agent:

| What you say | Agent triggered |
|---|---|
| "What is dollar-cost averaging?" | QA Agent (RAG) |
| "Explain the difference between a Roth and Traditional IRA" | Tax Agent + QA Agent |
| "Analyze my portfolio and suggest rebalancing" | Portfolio Agent |
| "What is NVDA trading at right now?" | Market Agent |
| "I want to retire at 55 with $2M — what should I save monthly?" | Goals Agent (Monte Carlo) |
| "What's happening with the Fed today?" | News Agent + Synthesizer |
| "How do capital gains taxes work?" | Tax Agent (RAG) |

Multi-turn conversations work naturally — follow-up questions use the full conversation history.

## Testing

```bash
# Run all tests
pytest tests/ --cov=src --cov-report=term

# Unit tests only (no services needed)
pytest tests/unit/ -q

# With coverage threshold
pytest tests/ --cov=src --cov-fail-under=70
```

The test suite has **163 tests** across 18 files at **75% line coverage**. Coverage includes all six agents, ChromaDB RAG store, adapter registry fallthrough, LLM factory (all providers), synthesizer, persistence node, and API routes (auth, portfolio, goals, market, health, settings). Integration tests use SQLite in-memory and an in-process cache — no external services needed.

## RAG Implementation

Financial education articles live in `src/rag/seed/` organised into five categories: `investing`, `portfolio`, `market`, `goals`, `tax` (51 articles total). At startup (or via the seed command) `src/rag/ingest.py` chunks each article into ~800-word overlapping segments, embeds them with `sentence-transformers/all-MiniLM-L6-v2`, and stores them in ChromaDB with category metadata.

At query time the LangGraph supervisor selects the relevant categories and passes them to `ChromaStore.query()`, which applies a metadata filter so the QA Agent only retrieves investing/portfolio docs, the Tax Agent only retrieves tax docs, and so on. Source title and URL are stored as metadata and included in the `citations` field of every agent response.

```
User query
  → Supervisor selects categories (e.g. ["tax", "investing"])
  → ChromaStore.query(text, categories=["tax", "investing"], k=5)
  → Top-5 chunks returned with metadata
  → Agent prompt includes chunks + source attribution
  → Response includes citations list
```

## Agent Communication

All agents communicate through a shared **LangGraph state dict** (`src/agents/state.py`). The flow for every user message:

1. **Supervisor** (`supervisor.py`) — LLM call that returns JSON: `{selected_agents, rag_categories, confidence, needs_clarification}`
2. **RAG retrieval** — ChromaDB queried for the selected categories; results stored in `state["retrieved_docs"]`
3. **Agent execution** — selected agents run concurrently via `asyncio.gather`; each appends to `state["agent_results"]`
4. **Synthesizer** (`synthesizer.py`) — merges parallel agent outputs into a single coherent response; appends regulatory disclaimer
5. **Persistence** — LangGraph checkpointer saves state to PostgreSQL so conversation history survives reconnects

```
Supervisor → RAG → [QA ‖ Portfolio ‖ Market ‖ Goals ‖ News ‖ Tax] → Synthesizer → WebSocket stream
```

## Performance Considerations

- **Market quotes** are cached in Redis for 60 seconds (configurable via `cache_ttl_market` in `config.yaml`). Subsequent requests for the same symbol within the window are served from cache with ~50ms latency.
- **News results** are cached per query for 5 minutes to avoid hammering the Google News RSS feed.
- **RAG retrieval** returns the top 5 chunks by cosine similarity. Increasing `n_results` in `ChromaStore.query()` improves recall at the cost of a larger LLM prompt.
- **Monte Carlo projections** run 1,000 simulations synchronously. For very high simulation counts (>10,000) consider offloading to a background task queue.
- **LangGraph state** is persisted in PostgreSQL via `langgraph-checkpoint-postgres`. For high concurrency, ensure the PostgreSQL connection pool is sized appropriately (`DATABASE_URL` pool settings in `config.yaml`).
- **Embedding model** (`all-MiniLM-L6-v2`) runs locally. First startup downloads ~90 MB; subsequent starts are instant from the local cache.

## Troubleshooting

**ChromaDB: collection not found or empty responses**
```bash
docker compose --profile seed up rag-ingest
# or locally:
python -m src.rag.ingest --seed-dir src/rag/seed --clear
```

**LLM auth error / 401 from Anthropic or OpenAI**
Check that `LLM_PROVIDER` and the matching API key are set correctly in `.env`. The key names are `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`.

**Redis connection refused**
```bash
docker compose up redis -d
# verify:
docker compose ps redis
```

**yfinance returns 0.0 prices or empty quotes**
yfinance is rate-limited by Yahoo Finance. Wait 60 seconds and retry. If Alpha Vantage is configured (`ALPHA_VANTAGE_API_KEY` in `.env`), the registry will fall through to it automatically.

**Database migration errors on startup**
```bash
docker compose exec api alembic upgrade head
```

**Full reset (wipe all data)**
```bash
docker compose down -v   # removes volumes
docker compose up -d
docker compose --profile seed up rag-ingest
```

**Frontend shows "WebSocket disconnected"**
The chat uses a persistent WebSocket. If the backend restarts mid-conversation, refresh the page — the conversation history is loaded from PostgreSQL.

**Port conflicts**
- Backend defaults to `8000`, frontend to `5173`, ChromaDB to `8001`, PostgreSQL to `5432`, Redis to `6379`.
- Override any port in `docker-compose.yml` or set `VITE_API_URL` in `ui/.env.local` for the frontend.

## Disclaimer

Aurum provides financial education only. Nothing here constitutes personalized investment or tax advice. Always consult a licensed financial advisor before making investment decisions.
