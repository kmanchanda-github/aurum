# Aurum MCP Server

Exposes Aurum's finance tools via the **Model Context Protocol (MCP)**, enabling
Claude Desktop and other MCP clients to query live market data, search the financial
knowledge base, analyze portfolios, and run Monte Carlo goal projections.

---

## Tools

| Tool | What it does |
|---|---|
| `get_stock_quote` | Live price, change, 52-week range for any ticker |
| `get_market_overview` | S&P 500, NASDAQ, Dow Jones snapshot |
| `get_stock_history` | OHLCV bars for any period (1d → max) |
| `search_financial_news` | Recent news via Google News RSS |
| `search_knowledge_base` | Semantic search over 51 finance articles |
| `analyze_portfolio` | P&L, allocation, live prices for a list of holdings |
| `calculate_goal_projection` | Monte Carlo simulation (p10/p50/p90, success probability) |
| `ask_finance_question` | RAG-grounded answer with source passages |

---

## Quick Start

### 1. Install dependencies

```bash
cd /path/to/Aurum
pip install -e ".[mcp]"          # adds fastmcp
# or with uv:
uv pip install -e ".[mcp]"
```

### 2. Seed the knowledge base (one-time)

The `search_knowledge_base` and `ask_finance_question` tools require ChromaDB.
If you have Docker running:

```bash
docker compose up chromadb -d
docker compose --profile seed up rag-ingest
```

Or run without ChromaDB — the other 6 tools work standalone with no infrastructure.

### 3. Run the server

**stdio (Claude Desktop default):**
```bash
python3 -m mcp_server.server
```

**streamable-http (remote/browser access):**
```bash
MCP_TRANSPORT=streamable-http python3 -m mcp_server.server
# Binds to 0.0.0.0:8002 by default
```

---

## Claude Desktop Setup

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "aurum-finance": {
      "command": "python3",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/Aurum",
      "env": {
        "USE_IN_MEMORY_CACHE": "true"
      }
    }
  }
}
```

Restart Claude Desktop. You'll see the Aurum tools available in the tools menu.

**With ChromaDB for RAG tools:**
```json
{
  "mcpServers": {
    "aurum-finance": {
      "command": "python3",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/Aurum",
      "env": {
        "USE_IN_MEMORY_CACHE": "true",
        "CHROMA_HOST": "localhost",
        "CHROMA_PORT": "8001"
      }
    }
  }
}
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | Transport: `stdio` or `streamable-http` |
| `MCP_HOST` | `0.0.0.0` | Bind host (streamable-http only) |
| `MCP_PORT` | `8002` | Bind port (streamable-http only) |
| `MCP_API_KEY` | *(unset)* | If set, all HTTP requests must include `X-API-Key: <value>` |
| `USE_IN_MEMORY_CACHE` | `true` | Use in-process cache instead of Redis |
| `CHROMA_HOST` | `localhost` | ChromaDB host (for RAG tools) |
| `CHROMA_PORT` | `8001` | ChromaDB port |

---

## Remote HTTP Deployment

For team or browser-based access, run with the streamable-http transport and protect
with an API key:

```bash
MCP_TRANSPORT=streamable-http \
MCP_HOST=0.0.0.0 \
MCP_PORT=8002 \
MCP_API_KEY=your-secret-key \
python3 -m mcp_server.server
```

Clients must include `X-API-Key: your-secret-key` in every request.

**Docker Compose addition** — add to `docker-compose.yml`:
```yaml
  mcp:
    build: .
    command: python3 -m mcp_server.server
    ports:
      - "8002:8002"
    environment:
      MCP_TRANSPORT: streamable-http
      MCP_HOST: 0.0.0.0
      MCP_PORT: "8002"
      MCP_API_KEY: ${MCP_API_KEY:-}
      USE_IN_MEMORY_CACHE: "false"
      REDIS_URL: redis://redis:6379/0
      CHROMA_HOST: chroma
      CHROMA_PORT: "8000"
    depends_on:
      - redis
      - chroma
```

---

## Example Conversations with Claude Desktop

Once connected, you can ask Claude:

> *"What is Apple trading at right now and how has it performed over the last 3 months?"*
→ Uses `get_stock_quote` + `get_stock_history`

> *"I'm 35, have $80k saved, can contribute $3k/month, and want $2M by retirement at 65. What are my chances?"*
→ Uses `calculate_goal_projection` (Monte Carlo, 30 years)

> *"Analyze my portfolio: 15 shares of NVDA at $400 cost basis, 50 shares of VTI at $200, 20 shares of BND at $80."*
→ Uses `analyze_portfolio`

> *"How does tax-loss harvesting work?"*
→ Uses `ask_finance_question` (RAG over knowledge base)

> *"What's happening with the Fed today?"*
→ Uses `search_financial_news`

---

## Tools That Need No Infrastructure

These work standalone (no Docker, no ChromaDB, no Redis):

- `get_stock_quote` — yfinance (internet required)
- `get_market_overview` — yfinance (internet required)
- `get_stock_history` — yfinance (internet required)
- `search_financial_news` — Google News RSS (internet required)
- `analyze_portfolio` — yfinance (internet required)
- `calculate_goal_projection` — pure NumPy, fully offline

These require ChromaDB running:
- `search_knowledge_base`
- `ask_finance_question`
