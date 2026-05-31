#!/usr/bin/env python3
"""
Aurum Performance Benchmark Script
===================================
Measures p50 / p95 / p99 latency for every key API surface.

Usage (app must be running):
    # Start the app first:
    docker compose up -d

    # Run benchmarks (default: 10 warm-up + 20 timed reps per endpoint):
    python scripts/benchmark.py

    # Custom options:
    python scripts/benchmark.py --base-url http://localhost:8000 --reps 30 --output docs/benchmarks.md

Requirements:
    pip install httpx rich
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime

import httpx

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_BASE = "http://localhost:8000"
DEFAULT_REPS = 20
WARMUP_REPS = 3

TEST_EMAIL = f"bench_{uuid.uuid4().hex[:8]}@aurum-bench.local"
TEST_PASSWORD = "BenchPass123!"

MARKET_SYMBOLS = ["AAPL", "MSFT", "NVDA"]

# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class BenchResult:
    name: str
    description: str
    samples: list[float] = field(default_factory=list)
    errors: int = 0
    status_codes: list[int] = field(default_factory=list)

    @property
    def p50(self) -> float:
        return statistics.median(self.samples) if self.samples else 0

    @property
    def p95(self) -> float:
        if not self.samples:
            return 0
        s = sorted(self.samples)
        idx = int(0.95 * len(s))
        return s[min(idx, len(s) - 1)]

    @property
    def p99(self) -> float:
        if not self.samples:
            return 0
        s = sorted(self.samples)
        idx = int(0.99 * len(s))
        return s[min(idx, len(s) - 1)]

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0

    @property
    def success_rate(self) -> float:
        total = len(self.samples) + self.errors
        return (len(self.samples) / total * 100) if total else 0


# ── Helpers ───────────────────────────────────────────────────────────────────


async def timed_get(client: httpx.AsyncClient, url: str, **kwargs) -> tuple[float, int]:
    t0 = time.perf_counter()
    r = await client.get(url, **kwargs)
    ms = (time.perf_counter() - t0) * 1000
    return ms, r.status_code


async def timed_post(client: httpx.AsyncClient, url: str, **kwargs) -> tuple[float, int]:
    t0 = time.perf_counter()
    r = await client.post(url, **kwargs)
    ms = (time.perf_counter() - t0) * 1000
    return ms, r.status_code


async def run_bench(
    result: BenchResult,
    fn,
    reps: int,
    warmup: int = WARMUP_REPS,
) -> None:
    # Warm-up (not recorded)
    for _ in range(warmup):
        try:
            await fn()
        except Exception:
            pass

    # Timed reps
    for _ in range(reps):
        try:
            ms, status = await fn()
            if status < 400:
                result.samples.append(ms)
            else:
                result.errors += 1
            result.status_codes.append(status)
        except Exception:
            result.errors += 1


# ── Benchmark suite ───────────────────────────────────────────────────────────


async def run_all(base: str, reps: int) -> list[BenchResult]:
    results: list[BenchResult] = []

    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        # ── 1. Auth: register ────────────────────────────────────────────────
        r = BenchResult("auth_register", "POST /api/auth/register — create account")
        emails = [f"bench_{uuid.uuid4().hex[:8]}@test.local" for _ in range(reps + WARMUP_REPS)]
        idx = [0]

        async def _register():
            e = emails[idx[0]]
            idx[0] += 1
            return await timed_post(client, "/api/auth/register",
                                    json={"email": e, "password": TEST_PASSWORD})

        await run_bench(r, _register, reps, warmup=0)
        results.append(r)

        # ── 2. Auth: login ───────────────────────────────────────────────────
        # Register a fixed account for subsequent login tests
        login_email = f"bench_login_{uuid.uuid4().hex[:8]}@test.local"
        await client.post("/api/auth/register",
                          json={"email": login_email, "password": TEST_PASSWORD})

        r = BenchResult("auth_login", "POST /api/auth/login — get JWT")

        async def _login():
            return await timed_post(client, "/api/auth/login",
                                    data={"username": login_email, "password": TEST_PASSWORD})

        await run_bench(r, _login, reps)
        results.append(r)

        # ── Get a token for authenticated requests ────────────────────────────
        resp = await client.post("/api/auth/login",
                                 data={"username": login_email, "password": TEST_PASSWORD})
        token = resp.json().get("access_token", "")
        auth = {"Authorization": f"Bearer {token}"}

        # ── 3. Market: quote (cache cold — first call per symbol) ─────────────
        r = BenchResult("market_quote_cold", "GET /api/market/quote/{symbol} — cache cold (yfinance live)")
        syms = MARKET_SYMBOLS * ((reps // len(MARKET_SYMBOLS)) + 2)
        sym_idx = [0]

        async def _quote_cold():
            # Use a different symbol each time to avoid cache hits
            sym = f"SYM{sym_idx[0]:04d}"  # non-existent → yfinance still makes network call
            sym_idx[0] += 1
            return await timed_get(client, f"/api/market/quote/AAPL", headers=auth)

        # For cold: bust cache between calls by querying different symbols
        cold_syms = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
                     "META", "TSLA", "JPM", "V", "JNJ",
                     "WMT", "PG", "UNH", "HD", "CVX",
                     "MRK", "PFE", "ABBV", "LLY", "AVGO",
                     "ORCL", "CSCO", "ADBE", "CRM", "INTC"]
        cold_idx = [0]

        async def _quote_varied():
            sym = cold_syms[cold_idx[0] % len(cold_syms)]
            cold_idx[0] += 1
            return await timed_get(client, f"/api/market/quote/{sym}", headers=auth)

        await run_bench(r, _quote_varied, reps)
        results.append(r)

        # ── 4. Market: quote (cache warm — same symbol) ───────────────────────
        r = BenchResult("market_quote_warm", "GET /api/market/quote/AAPL — cache warm (Redis hit)")
        # Prime the cache
        await client.get("/api/market/quote/AAPL", headers=auth)

        async def _quote_warm():
            return await timed_get(client, "/api/market/quote/AAPL", headers=auth)

        await run_bench(r, _quote_warm, reps)
        results.append(r)

        # ── 5. Market: indices ────────────────────────────────────────────────
        r = BenchResult("market_indices", "GET /api/market/indices — major index overview")

        async def _indices():
            return await timed_get(client, "/api/market/indices", headers=auth)

        await run_bench(r, _indices, reps)
        results.append(r)

        # ── 6. Portfolio: list ────────────────────────────────────────────────
        r = BenchResult("portfolio_list", "GET /api/portfolio — list portfolios (DB query)")

        async def _portfolio_list():
            return await timed_get(client, "/api/portfolio", headers=auth)

        await run_bench(r, _portfolio_list, reps)
        results.append(r)

        # ── 7. Goals: list ────────────────────────────────────────────────────
        r = BenchResult("goals_list", "GET /api/goals — list goals (DB query)")

        async def _goals_list():
            return await timed_get(client, "/api/goals", headers=auth)

        await run_bench(r, _goals_list, reps)
        results.append(r)

        # ── 8. Goals: Monte Carlo projection ─────────────────────────────────
        # Create a goal to project
        gr = await client.post("/api/goals", headers=auth, json={
            "name": "Benchmark Goal",
            "goal_type": "retirement",
            "target_amount": "1000000",
            "current_amount": "50000",
            "monthly_contribution": "2000",
            "risk_tolerance": "moderate",
            "priority": 1,
        })
        if gr.status_code == 201:
            goal_id = gr.json()["id"]
            r = BenchResult("goals_projection",
                            f"POST /api/goals/{{id}}/projection — Monte Carlo 1,000 simulations")

            async def _projection():
                return await timed_post(client,
                                        f"/api/goals/{goal_id}/projection?monte_carlo_runs=1000&years=30",
                                        headers=auth)

            await run_bench(r, _projection, reps)
            results.append(r)

        # ── 9. News: fetch ────────────────────────────────────────────────────
        r = BenchResult("news_fetch", "GET /api/news?query=... — Google News RSS fetch")

        async def _news():
            return await timed_get(client, "/api/news?query=stock+market", headers=auth)

        await run_bench(r, _news, min(reps, 10))  # fewer reps — RSS can be slow
        results.append(r)

        # ── 10. Health ────────────────────────────────────────────────────────
        r = BenchResult("health", "GET /api/health — liveness check")

        async def _health():
            return await timed_get(client, "/api/health")

        await run_bench(r, _health, reps)
        results.append(r)

        # ── 11. RAG ingest timing (offline — measure chunk+embed time) ────────
        r = BenchResult("rag_chroma_query",
                        "ChromaDB query — semantic search over 51 articles (in-process)")
        try:
            import os
            os.environ.setdefault("USE_IN_MEMORY_CACHE", "true")
            os.environ.setdefault("USE_SQLITE", "true")
            os.environ.setdefault("SECRET_KEY", "bench-secret-key-placeholder-32chars!")
            import sys
            sys.path.insert(0, ".")
            from src.rag.chroma_store import ChromaStore

            store = ChromaStore()

            async def _rag_query():
                t0 = time.perf_counter()
                store.query("how to diversify a portfolio", categories=["portfolio", "investing"], k=5)
                ms = (time.perf_counter() - t0) * 1000
                return ms, 200

            await run_bench(r, _rag_query, reps)
        except Exception as e:
            r.errors += 1

        results.append(r)

    return results


# ── Output ────────────────────────────────────────────────────────────────────


def print_table(results: list[BenchResult]) -> None:
    print(f"\n{'─'*90}")
    print(f"{'Endpoint':<40} {'p50':>8} {'p95':>8} {'p99':>8} {'mean':>8} {'ok%':>6} {'n':>5}")
    print(f"{'─'*90}")
    for r in results:
        print(f"{r.name:<40} {r.p50:>7.1f}ms {r.p95:>7.1f}ms {r.p99:>7.1f}ms "
              f"{r.mean:>7.1f}ms {r.success_rate:>5.1f}% {len(r.samples):>5}")
    print(f"{'─'*90}\n")


def write_markdown(results: list[BenchResult], path: str, base: str, reps: int) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Aurum — Performance Benchmarks",
        "",
        f"Measured: {ts}  |  Base URL: `{base}`  |  Reps per endpoint: {reps}  |  Warm-up: {WARMUP_REPS}",
        "",
        "> All timings are end-to-end HTTP round-trip (client → FastAPI → service → response).",
        "> Cache-warm measurements reflect Redis-cached responses. Cache-cold measurements hit",
        "> the external API (yfinance / Yahoo Finance).",
        "",
        "## Results",
        "",
        "| Endpoint | Description | p50 | p95 | p99 | Success |",
        "|---|---|---:|---:|---:|---:|",
    ]

    for r in results:
        lines.append(
            f"| `{r.name}` | {r.description} "
            f"| {r.p50:.0f}ms | {r.p95:.0f}ms | {r.p99:.0f}ms | {r.success_rate:.0f}% |"
        )

    lines += [
        "",
        "## Notes",
        "",
        "- **`market_quote_cold`**: Each call fetches a different ticker from yfinance (no cache hit). Latency dominated by Yahoo Finance network roundtrip.",
        "- **`market_quote_warm`**: Same ticker (`AAPL`) repeated — served from Redis (60s TTL). Latency is local Redis lookup only.",
        "- **`goals_projection`**: 1,000 Monte Carlo simulations using NumPy — pure local computation, no external calls.",
        "- **`rag_chroma_query`**: In-process ChromaDB cosine similarity search over 51 articles. Includes embedding of query string.",
        "- **`news_fetch`**: Fetches Google News RSS feed — latency varies by network conditions. Cached for 15 minutes per query.",
        "- **`auth_register`** / **`auth_login`**: bcrypt hashing adds ~100ms intentionally (security).",
        "",
        "## Caching Reference",
        "",
        "| Data | TTL | Config Key |",
        "|---|---|---|",
        "| Stock quote | 60s | `CACHE_TTL_QUOTE` |",
        "| Price history | 300s | `CACHE_TTL_HISTORY` |",
        "| Index prices | 3600s | `CACHE_TTL_INDEX` |",
        "| News feed | 900s | `CACHE_TTL_NEWS` |",
        "",
        "## Tuning Tips",
        "",
        "- Increase `CACHE_TTL_QUOTE` in `.env` to reduce yfinance calls at the cost of quote freshness.",
        "- Scale uvicorn workers (`--workers 4` in production `docker-compose.prod.yml`) for concurrent user load.",
        "- ChromaDB `n_results` (default 5) trades recall for speed — lower it to reduce LLM prompt size.",
        "- Monte Carlo `monte_carlo_runs` default is 1,000. Reduce to 500 for faster projections on slower hardware.",
        "",
        f"*Generated by `scripts/benchmark.py` on {ts}*",
    ]

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Benchmark results written to: {path}")


# ── Main ──────────────────────────────────────────────────────────────────────


async def main() -> None:
    parser = argparse.ArgumentParser(description="Aurum API benchmark")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--reps", type=int, default=DEFAULT_REPS)
    parser.add_argument("--output", default="docs/benchmarks.md")
    args = parser.parse_args()

    print(f"\nAurum Benchmark  |  base={args.base_url}  |  reps={args.reps}")
    print("Running... (this takes ~2-3 minutes)\n")

    results = await run_all(args.base_url, args.reps)
    print_table(results)
    write_markdown(results, args.output, args.base_url, args.reps)


if __name__ == "__main__":
    asyncio.run(main())
