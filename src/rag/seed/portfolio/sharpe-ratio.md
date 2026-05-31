---
source_title: Understanding the Sharpe Ratio
category: portfolio
source_url: ""
---

# Understanding the Sharpe Ratio

The Sharpe ratio is the most widely used measure of risk-adjusted return. It tells you how much return you're earning per unit of risk taken — helping you compare two portfolios not just by their raw returns, but by how efficiently those returns were achieved.

## The Formula

**Sharpe Ratio = (Portfolio Return − Risk-Free Rate) ÷ Portfolio Standard Deviation**

- **Portfolio Return**: Your actual annualized return
- **Risk-Free Rate**: The return on a "safe" investment (typically the 3-month US Treasury bill, currently ~5%)
- **Standard Deviation**: A measure of how volatile your portfolio returns are

## Reading the Sharpe Ratio

| Sharpe Ratio | Interpretation |
|---|---|
| Below 1.0 | Poor risk-adjusted return |
| 1.0 – 1.99 | Good — acceptable risk per unit of return |
| 2.0 – 2.99 | Very good |
| 3.0+ | Excellent (rare in practice) |

## Why It Matters

**Example**: Two portfolios both returned 12% last year.
- Portfolio A had a standard deviation of 8% → Sharpe = (12% − 5%) ÷ 8% = **0.88**
- Portfolio B had a standard deviation of 4% → Sharpe = (12% − 5%) ÷ 4% = **1.75**

Portfolio B achieved the same return with half the volatility. It's the better investment on a risk-adjusted basis. The Sharpe ratio reveals this; raw returns don't.

## Practical Use Cases

**Comparing funds**: An actively managed fund returning 14% with high volatility might have a lower Sharpe ratio than an index fund returning 11% with low volatility.

**Evaluating portfolio changes**: Adding a new asset class is worth it if it raises your portfolio's Sharpe ratio — i.e., the added return outweighs the added risk.

**Assessing managers**: Hedge funds often advertise raw returns. The Sharpe ratio tells you whether those returns came with excessive risk-taking.

## Limitations

**Assumes normal distribution**: Returns in financial markets have "fat tails" — extreme events happen more often than a bell curve predicts. The Sharpe ratio doesn't fully capture this.

**Historical only**: A high past Sharpe ratio doesn't guarantee future performance.

**Penalizes upside volatility**: The Sharpe ratio treats positive surprise returns the same as negative ones as "risk." The Sortino ratio (which only penalizes downside volatility) addresses this.

**Risk-free rate sensitivity**: When the risk-free rate is high (like in 2023–2024), even decent portfolios show lower Sharpe ratios because the benchmark is higher.

## Related Metrics

- **Sortino Ratio**: Like Sharpe, but only counts downside volatility — more intuitive for investors
- **Treynor Ratio**: Uses beta (market risk) instead of standard deviation — useful for comparing funds in the same asset class
- **Calmar Ratio**: Return divided by maximum drawdown — useful for evaluating strategies over crash periods

## Practical Takeaway

When evaluating any investment or portfolio, don't just look at returns. Ask: "How much risk did I take to get there?" The Sharpe ratio provides that answer. A broad market index fund consistently achieves Sharpe ratios of 0.5–1.0 over long periods — a useful benchmark.
