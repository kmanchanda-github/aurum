# Aurum — Performance Benchmarks

Measured: 2026-05-30 | Hardware: MacBook Pro M3 | Python 3.14

> **How to read this table**: p50 is the median (typical case). p95 is the 95th percentile (worst 1-in-20 request).
> Starred rows (★) are directly measured. Others are representative estimates based on component benchmarks
> and are validated when the full Docker stack is running.

---

## Measured Results (In-Process / Component Level)

These were benchmarked directly without Docker overhead — representative of the compute-only cost of each operation.

| Component | Operation | p50 | p95 | Notes |
|---|---|---:|---:|---|
| ★ Auth | bcrypt hash + verify | 472ms | 473ms | Intentional — security cost. Same for register + login. |
| ★ RAG | ChromaDB cosine query (51 articles, category filter) | 114ms | 120ms | Includes query embedding via `all-MiniLM-L6-v2` |
| ★ Goals | Monte Carlo projection (1,000 simulations, 30 years) | 10ms | 11ms | Pure NumPy, no I/O |
| ★ Goals | Monte Carlo projection (500 simulations, 30 years) | 8ms | 8ms | Faster alternative for mobile/slow clients |
| ★ DB | Portfolio list (SQLite, in-process) | 2ms | 16ms | PostgreSQL in Docker adds ~5–15ms |
| ★ DB | Goals list (SQLite, in-process) | 2ms | 3ms | PostgreSQL in Docker adds ~5–15ms |

---

## Full Stack Estimates (Docker + FastAPI + PostgreSQL + Redis)

These include FastAPI routing, auth middleware, DB connection pool overhead, and network to Docker containers.

| Endpoint | Description | p50 est. | p95 est. |
|---|---|---:|---:|
| `GET /api/health` | Liveness check | ~5ms | ~15ms |
| `POST /api/auth/register` | bcrypt + DB write | ~490ms | ~510ms |
| `POST /api/auth/login` | bcrypt verify + JWT sign | ~480ms | ~500ms |
| `GET /api/market/quote/{symbol}` — **cache warm** | Redis hit (60s TTL) | ~15ms | ~35ms |
| `GET /api/market/quote/{symbol}` — **cache cold** | yfinance live fetch | ~400ms | ~900ms |
| `GET /api/market/indices` | 3–5 symbols, mixed cache | ~50ms | ~250ms |
| `GET /api/portfolio` | DB query, holdings join | ~10ms | ~30ms |
| `GET /api/goals` | DB query, ordered list | ~8ms | ~20ms |
| `POST /api/goals/{id}/projection` | Monte Carlo 1,000 runs | ~25ms | ~40ms |
| `GET /api/news?query=...` — **cache warm** | Redis hit (15m TTL) | ~10ms | ~25ms |
| `GET /api/news?query=...` — **cache cold** | Google News RSS fetch | ~600ms | ~1,500ms |
| `WS /api/chat/ws` — **supervisor routing** | LLM JSON routing decision | ~900ms | ~1,800ms |
| `WS /api/chat/ws` — **QA agent (RAG)** | RAG retrieval + LLM generation | ~2,000ms | ~3,500ms |
| `WS /api/chat/ws` — **market agent** | Live quote + LLM generation | ~1,200ms | ~2,200ms |
| `WS /api/chat/ws` — **goals agent** | Monte Carlo + LLM generation | ~1,500ms | ~2,800ms |
| `WS /api/chat/ws` — **multi-agent (2 agents)** | Parallel + synthesizer | ~2,500ms | ~4,500ms |

> **Chat latency notes**: WebSocket chat streams tokens as they arrive — the user sees the first token in ~800–1,200ms
> (supervisor + RAG) and the full response completes at the times above. Latency is dominated by the LLM provider
> (Anthropic / OpenAI), not Aurum's infrastructure.

---

## Caching Reference

| Data | TTL | Config key | Backend |
|---|---|---|---|
| Stock quote | 60s | `CACHE_TTL_QUOTE` | Redis |
| Price history | 300s | `CACHE_TTL_HISTORY` | Redis |
| Index prices | 3,600s | `CACHE_TTL_INDEX` | Redis |
| News feed | 900s | `CACHE_TTL_NEWS` | Redis |

Override any TTL in `.env`. Set `USE_IN_MEMORY_CACHE=true` to use `cachetools.TTLCache` instead of Redis (for Hugging Face Spaces or local dev without Redis).

---

## Running Benchmarks Yourself

```bash
# 1. Start the full stack
docker compose up -d
docker compose --profile seed up rag-ingest

# 2. Install httpx if not already installed
pip install httpx

# 3. Run the benchmark script
python scripts/benchmark.py

# 4. Custom options
python scripts/benchmark.py --base-url http://localhost:8000 --reps 30 --output docs/benchmarks.md
```

The script registers a temporary user, runs each endpoint with warm-up reps, then records p50/p95/p99 over the configured number of repetitions.

---

## Tuning Tips

**Reducing yfinance latency**
- Increase `CACHE_TTL_QUOTE` (e.g. `120`) to serve from Redis longer. Quotes will be up to 2 minutes stale.
- Enable Alpha Vantage as a fallback (`ALPHA_VANTAGE_API_KEY` in `.env`) — it provides a secondary data source if yfinance is rate-limited.

**Reducing LLM latency**
- Use `gpt-4o-mini` or `claude-haiku-4-5` instead of larger models — 3–5× faster for routing decisions.
- `LLM_TEMPERATURE=0` removes sampling randomness and can slightly reduce latency on some providers.

**Scaling for concurrent users**
- Production `docker-compose.prod.yml` runs 4 uvicorn workers (`--workers 4`).
- Each worker handles requests concurrently via `asyncio` — a single worker can handle ~50 concurrent WebSocket connections.
- PostgreSQL connection pool is sized at 10 connections per worker by default; increase `DATABASE_POOL_SIZE` in `config.yaml` for higher concurrency.

**Monte Carlo speed**
- Default 1,000 simulations takes ~10ms of CPU. Reduce to 500 for 20% speed gain with minimal accuracy loss.
- For >10,000 simulations, move to a background task (Celery/ARQ) to avoid blocking the event loop.

**ChromaDB retrieval**
- Default `n_results=5` — each additional result adds ~5ms and increases LLM prompt size.
- Category filtering significantly improves both speed and answer quality by reducing the search space.

---

*Benchmarks generated on MacBook Pro M3, 2026-05-30. Network latency to LLM providers excluded from component-level measurements.*
