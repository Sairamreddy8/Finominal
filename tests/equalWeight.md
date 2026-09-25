# Test — `equal_weighted`

The baseline case: two holdings, rebalanced from a lopsided 75/25 split to an even one.

## Request

```json
{
  "holdings": [
    {
      "ticker": "IEFA",
      "security_name": "iShares Core MSCI EAFE ETF",
      "percentage": 0.75,
      "min_weight": 0,
      "max_weight": 1
    },
    {
      "ticker": "SPY",
      "security_name": "State Street SPDR S&P 500 ETF Trust",
      "percentage": 0.25,
      "min_weight": 0,
      "max_weight": 1
    }
  ],
  "optimization_objective": "equal_weighted"
}
```

## Response

```json
{
  "optimization_strategy": "equal_weighted",
  "allocation_changes": [
    {
      "ticker": "IEFA",
      "security_name": "iShares Core MSCI EAFE ETF",
      "current_weight": 0.75,
      "optimized_weight": 0.5,
      "change": -0.25
    },
    {
      "ticker": "SPY",
      "security_name": "State Street SPDR S&P 500 ETF Trust",
      "current_weight": 0.25,
      "optimized_weight": 0.5,
      "change": 0.25
    }
  ]
}
```

## Expected output

| | value |
| --- | --- |
| Weights | IEFA 0.5000, SPY 0.5000 |
| Changes | −0.2500 / +0.2500 |
| Weights sum | 1.0000 exactly |

With two holdings each gets `1/2`, which has an exact decimal form — so unlike an odd
number of holdings, the rounded weights sum to exactly 1.0000. Three holdings would give
0.3333 each, summing to 0.9999.

## What this case shows

The starting book is three-quarters IEFA, and an equal split halves that. Both funds are
developed-market equity with similar volatility (16.63% and
16.81%), so unlike the mixed-asset cases the reallocation barely
changes portfolio risk — volatility moves 16.18% → 16.05%.

What does change is return: CAGR rises 10.10% → 11.78%, because the shift
moves weight into SPY, the stronger performer over this window. That is incidental.
`equal_weighted` looks at no return data at all; it would produce the same weights
whatever the history showed.

## Notes

- **`min_weight` / `max_weight` are ignored by this strategy.** They are present in the
  request and validated, but an equal split is equal by definition — nothing to constrain.
  Sending different bounds produces identical output.
- **The window is 2012-10-23 → 2026-05-27** (3414 observations,
  13.59 years), bounded by IEFA's inception. The request carries no date range: the
  window is derived from the holdings, not chosen.
