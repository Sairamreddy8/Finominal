# Test — `sharpe_ratio` with bounds and a dividend floor

The fully constrained case: five holdings, a 5% floor and 40% cap on every position, and
a 2.5% portfolio dividend-yield floor. Exercises both constraint kinds at once.

## Request

```json
{
  "holdings": [
    {
      "ticker": "AGG",
      "security_name": "iShares Core US Aggregate Bond ETF",
      "percentage": 0.2,
      "min_weight": 0.05,
      "max_weight": 0.4
    },
    {
      "ticker": "GLD",
      "security_name": "SPDR Gold Shares",
      "percentage": 0.2,
      "min_weight": 0.05,
      "max_weight": 0.4
    },
    {
      "ticker": "SPY",
      "security_name": "State Street SPDR S&P 500 ETF Trust",
      "percentage": 0.2,
      "min_weight": 0.05,
      "max_weight": 0.4
    },
    {
      "ticker": "VEA",
      "security_name": "Vanguard FTSE Developed Markets ETF",
      "percentage": 0.2,
      "min_weight": 0.05,
      "max_weight": 0.4
    },
    {
      "ticker": "IEFA",
      "security_name": "iShares Core MSCI EAFE ETF",
      "percentage": 0.2,
      "min_weight": 0.05,
      "max_weight": 0.4
    }
  ],
  "optimization_objective": "sharpe_ratio",
  "min_dividend_yield": 0.025
}
```

> `min_dividend_yield` is a **fraction** here — `0.025` means 2.5%. The reference request
> sends `2.5`; this API takes fractions throughout, matching `min_weight` and
> `percentage`.

## Response

```json
{
  "optimization_strategy": "sharpe_ratio",
  "allocation_changes": [
    {
      "ticker": "AGG",
      "security_name": "iShares Core US Aggregate Bond ETF",
      "current_weight": 0.2,
      "optimized_weight": 0.4,
      "change": 0.2
    },
    {
      "ticker": "GLD",
      "security_name": "SPDR Gold Shares",
      "current_weight": 0.2,
      "optimized_weight": 0.0703,
      "change": -0.1297
    },
    {
      "ticker": "SPY",
      "security_name": "State Street SPDR S&P 500 ETF Trust",
      "current_weight": 0.2,
      "optimized_weight": 0.3332,
      "change": 0.1332
    },
    {
      "ticker": "VEA",
      "security_name": "Vanguard FTSE Developed Markets ETF",
      "current_weight": 0.2,
      "optimized_weight": 0.05,
      "change": -0.15
    },
    {
      "ticker": "IEFA",
      "security_name": "iShares Core MSCI EAFE ETF",
      "current_weight": 0.2,
      "optimized_weight": 0.1465,
      "change": -0.0535
    }
  ]
}
```

## Expected output

| | value |
| --- | --- |
| Weights | AGG 0.4000, GLD 0.0703, SPY 0.3332, VEA 0.0500, IEFA 0.1465 |
| Changes | +0.2000 / −0.1297 / +0.1332 / −0.1500 / −0.0535 |
| Weights sum | 1.0000, none negative |
| Achieved yield | **2.4999%** — see the rounding note below |
| Sharpe | **0.9025** |
| Every bound | satisfied: all weights within 0.05 – 0.40 |

## What the constraints cost

Unconstrained, `sharpe_ratio` on these five holdings drops VEA and IEFA entirely and
reaches a Sharpe of **1.0311**. The bounds forbid that — nothing may fall
below 5% — and the yield floor forces more into the higher-yielding funds:

| | unconstrained | constrained | bound |
| --- | --- | --- | --- |
| AGG | 0.3480 | 0.4000 | 0.05 – 0.40 |
| GLD | 0.1983 | 0.0703 | 0.05 – 0.40 |
| SPY | 0.4537 | 0.3332 | 0.05 – 0.40 |
| VEA | 0.0000 | 0.0500 | 0.05 – 0.40 |
| IEFA | 0.0000 | 0.1465 | 0.05 – 0.40 |

Sharpe falls 1.0311 → **0.9025**. Constraints always cost
something against the objective; what they buy here is a portfolio that actually holds
all five securities and meets an income requirement.

## Why bounds go into the solver for this strategy

`min_volatility` and `min_drawdown` solve unconstrained and clamp the result into the
bounds afterwards. `sharpe_ratio` cannot: clamping weights after the fact could drag the
portfolio's dividend yield back below `min_dividend_yield`, returning something that
quietly violates the request. Its bounds are SLSQP bounds and its yield floor an
inequality constraint, so both hold simultaneously — as this case demonstrates.

## A rounding caveat worth knowing

The solver satisfies the yield floor **exactly** — its allocation yields 2.5000000000%.
But weights are reported to four decimals, and recomputing the yield from those rounded
figures gives **2.49989%**, about 1.1 parts per million short of the floor:

```
solver   0.4  0.07026074  0.33320733  0.05  0.14653193  ->  2.5000000000%
reported 0.4  0.0703      0.3332      0.05  0.1465      ->  2.4998880000%
```

This is inherent: weights cannot both be rounded for display and guarantee a tight
inequality holds on the rounded values. The shortfall is 0.0001 percentage points and has
no practical effect, but a validator re-deriving the yield from the response and applying
a strict `>=` will flag it. Compare with a small tolerance.

The weight bounds have no such issue — they are satisfied exactly before and after
rounding, because rounding moves each weight by less than the slack available.

## Feasibility

The highest yield reachable under these bounds is **3.15%**, found by seating every
holding at its 5% floor and then filling from highest yield down to the 40% cap. A floor
above that is rejected with **HTTP 422** naming the ceiling, before the solver runs.

## Notes

- **Three `maxWeight` values were truncated** in the source dump (`…`); all five are taken
  as `0.40`, matching GLD, the one shown in full.
- **The window is 2012-10-23 → 2026-05-27**, pinned by IEFA's inception. The request
  carries no date range; the holdings decide it.
