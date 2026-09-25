# Test — `min_volatility`

Three holdings with no binding bounds, so this is the unconstrained case: the calmest
allocation the optimizer can find.

## Request

```json
{
  "holdings": [
    {
      "ticker": "AGG",
      "security_name": "iShares Core US Aggregate Bond ETF",
      "percentage": 0.3,
      "min_weight": 0,
      "max_weight": 1
    },
    {
      "ticker": "GLD",
      "security_name": "SPDR Gold Shares",
      "percentage": 0.1,
      "min_weight": 0,
      "max_weight": 1
    },
    {
      "ticker": "SPY",
      "security_name": "State Street SPDR S&P 500 ETF Trust",
      "percentage": 0.6,
      "min_weight": 0,
      "max_weight": 1
    }
  ],
  "optimization_objective": "min_volatility"
}
```

## Response

```json
{
  "optimization_strategy": "min_volatility",
  "allocation_changes": [
    {
      "ticker": "AGG",
      "security_name": "iShares Core US Aggregate Bond ETF",
      "current_weight": 0.3,
      "optimized_weight": 0.912,
      "change": 0.612
    },
    {
      "ticker": "GLD",
      "security_name": "SPDR Gold Shares",
      "current_weight": 0.1,
      "optimized_weight": 0.0187,
      "change": -0.0813
    },
    {
      "ticker": "SPY",
      "security_name": "State Street SPDR S&P 500 ETF Trust",
      "current_weight": 0.6,
      "optimized_weight": 0.0693,
      "change": -0.5307
    }
  ]
}
```

## Expected output

|                     | value                              |
| ------------------- | ---------------------------------- |
| Weights             | AGG 0.9120, GLD 0.0187, SPY 0.0693 |
| Changes             | +0.6120 / −0.0813 / −0.5307        |
| Weights sum         | 1.0000, none negative              |
| Volatility achieved | **5.02%**, down from 11.76%        |

## What this case shows

The starting book is 60% SPY. Minimizing volatility inverts it almost completely —
**91.2% into AGG**, a swing of +0.61, with
SPY cut to 6.9%.

The reason is the volatility spread across the three:

|                       | AGG       | GLD    | SPY    |
| --------------------- | --------- | ------ | ------ |
| Annualized volatility | **5.21%** | 18.13% | 18.92% |
| Optimized weight      | 91.2%     | 1.9%   | 6.9%   |

AGG is roughly a third as volatile as the other two, so the calmest portfolio is
overwhelmingly AGG. Portfolio volatility more than halves, 11.76% →
**5.02%**.

The cost is return. CAGR falls 9.19% → 3.88%, and Sharpe with it,
0.8065 → 0.7851 — the optimized portfolio is _worse_
risk-adjusted than the one it replaced. That is not a bug: this strategy is told to make
volatility small and does so without regard to what it gives up. Use `sharpe_ratio` if
return per unit of risk is what matters.

## Notes

- **No bound binds here.** Every holding is left at the defaults (0 and 1), so the
  unconstrained optimum is returned as-is. `min_volatility` _does_ honour `min_weight` /
  `max_weight` when they are set — it solves unconstrained and then clamps the result
  into the bounds, redistributing the difference so the book still totals 100%. See
  `STRATEGIES.md`.
- **`min_dividend_yield` is a fraction** (`0.025` = 2.5%), unlike the reference API which
  sends `2.5`. It is applied by `sharpe_ratio` only, so it has no effect on this request.
- **The other portfolio-level constraints are accepted and ignored.** `min_cagr`,
  `max_volatility`, `min_volatility` and `max_drawdown` are carried above exactly as the
  reference sends them, in _percent_ (`8` = 8%, `-49` = −49%). They are not part of
  `OptimizationRequest`, so pydantic drops them. Implementing them will require the same
  percent-to-fraction conversion `min_dividend_yield` already went through.
- **The window is 2004-11-18 → 2026-05-27** (5413 observations,
  21.52 years), bounded by GLD's inception. The request carries no date range: the
  window is derived from the holdings, not chosen.
