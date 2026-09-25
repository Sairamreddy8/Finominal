# Test — `sharpe_ratio`

Five holdings at 20% each, optimized for return per unit of risk at a risk-free rate
of 0%. No bounds bind and no dividend floor is set, so this is the unconstrained case.

## Request

```json
{
  "holdings": [
    {
      "ticker": "AGG",
      "security_name": "iShares Core US Aggregate Bond ETF",
      "percentage": 0.2,
      "min_weight": 0,
      "max_weight": 1
    },
    {
      "ticker": "GLD",
      "security_name": "SPDR Gold Shares",
      "percentage": 0.2,
      "min_weight": 0,
      "max_weight": 1
    },
    {
      "ticker": "SPY",
      "security_name": "State Street SPDR S&P 500 ETF Trust",
      "percentage": 0.2,
      "min_weight": 0,
      "max_weight": 1
    },
    {
      "ticker": "VEA",
      "security_name": "Vanguard FTSE Developed Markets ETF",
      "percentage": 0.2,
      "min_weight": 0,
      "max_weight": 1
    },
    {
      "ticker": "IEFA",
      "security_name": "iShares Core MSCI EAFE ETF",
      "percentage": 0.2,
      "min_weight": 0,
      "max_weight": 1
    }
  ],
  "optimization_objective": "sharpe_ratio"
}
```

## Response

```json
{
  "optimization_strategy": "sharpe_ratio",
  "allocation_changes": [
    {
      "ticker": "AGG",
      "security_name": "iShares Core US Aggregate Bond ETF",
      "current_weight": 0.2,
      "optimized_weight": 0.348,
      "change": 0.148
    },
    {
      "ticker": "GLD",
      "security_name": "SPDR Gold Shares",
      "current_weight": 0.2,
      "optimized_weight": 0.1983,
      "change": -0.0017
    },
    {
      "ticker": "SPY",
      "security_name": "State Street SPDR S&P 500 ETF Trust",
      "current_weight": 0.2,
      "optimized_weight": 0.4537,
      "change": 0.2537
    },
    {
      "ticker": "VEA",
      "security_name": "Vanguard FTSE Developed Markets ETF",
      "current_weight": 0.2,
      "optimized_weight": 0.0,
      "change": -0.2
    },
    {
      "ticker": "IEFA",
      "security_name": "iShares Core MSCI EAFE ETF",
      "current_weight": 0.2,
      "optimized_weight": 0.0,
      "change": -0.2
    }
  ]
}
```

## Expected output

| | value |
| --- | --- |
| Weights | AGG 0.3480, GLD 0.1983, SPY 0.4537, VEA 0.0000, IEFA 0.0000 |
| Changes | +0.1480 / -0.0017 / +0.2537 / -0.2000 / -0.2000 |
| Weights sum | 1.0000, none negative |
| Sharpe achieved | **1.0311**, against 0.8204 for the equal-weighted starting book |

## What this case shows

**Two holdings are dropped entirely.** VEA and IEFA both fall to 0.0000. They are not
being penalised for poor returns in isolation — they are near-duplicates of SPY and of
each other, both developed-market equity funds. Once SPY is held at 45.4%, neither
adds diversification the optimizer values, so the allocation collapses onto three
holdings.

This is characteristic of `sharpe_ratio` and worth expecting: it optimizes on **mean
returns**, which are far noisier estimates than covariance, and it readily takes corner
solutions. Small changes to the window can move these weights substantially. The
risk-based strategies spread their reliance more evenly and are correspondingly steadier.

Sharpe rises from 0.8204 to 1.0311, with volatility falling
10.87% → 8.94% and CAGR 8.68% → 9.22%.

## Notes

- **The window is set by the holdings, not the request.** Including IEFA pins it to
  2012-10-23 — IEFA's inception. The request carries no date range; including IEFA is
  what pins the window, and the fund data stops at 2026-05-27.
- **The strategy is named `sharpe_ratio`**, matching the reference API. It was briefly
  called `max_sharpe` during development.
- **`min_dividend_yield` is accepted by this strategy only**, as a fraction
  (`0.03` = 3%). It is absent here, so no yield floor applies. See `STRATEGIES.md` for
  how it behaves when set.
- **Bounds are applied inside the solver** for this strategy rather than by clamping
  afterwards, because a yield floor and post-hoc clamping cannot both be honoured.
