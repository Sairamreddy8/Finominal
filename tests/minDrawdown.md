# Test — `min_drawdown`

Finds the allocation whose worst historical peak-to-trough fall is smallest.

## Request

```json
{
  "holdings": [
    {
      "ticker": "AGG",
      "security_name": "iShares Core US Aggregate Bond ETF",
      "percentage": 0.21,
      "min_weight": 0.02,
      "max_weight": 1
    },
    {
      "ticker": "GLD",
      "security_name": "SPDR Gold Shares",
      "percentage": 0.21,
      "min_weight": 0.02,
      "max_weight": 1
    },
    {
      "ticker": "SPY",
      "security_name": "State Street SPDR S&P 500 ETF Trust",
      "percentage": 0.19,
      "min_weight": 0.02,
      "max_weight": 1
    },
    {
      "ticker": "VEA",
      "security_name": "Vanguard FTSE Developed Markets ETF",
      "percentage": 0.39,
      "min_weight": 0.02,
      "max_weight": 1
    }
  ],
  "optimization_objective": "min_drawdown"
}
```

## Response

```json
{
  "optimization_strategy": "min_drawdown",
  "allocation_changes": [
    {
      "ticker": "AGG",
      "security_name": "iShares Core US Aggregate Bond ETF",
      "current_weight": 0.21,
      "optimized_weight": 0.5521,
      "change": 0.3421
    },
    {
      "ticker": "GLD",
      "security_name": "SPDR Gold Shares",
      "current_weight": 0.21,
      "optimized_weight": 0.3129,
      "change": 0.1029
    },
    {
      "ticker": "SPY",
      "security_name": "State Street SPDR S&P 500 ETF Trust",
      "current_weight": 0.19,
      "optimized_weight": 0.1151,
      "change": -0.0749
    },
    {
      "ticker": "VEA",
      "security_name": "Vanguard FTSE Developed Markets ETF",
      "current_weight": 0.39,
      "optimized_weight": 0.02,
      "change": -0.37
    }
  ]
}
```

## Expected output

|                       | value                                              |
| --------------------- | -------------------------------------------------- |
| Weights               | AGG 0.5521, GLD 0.3129, SPY 0.1151, VEA 0.0200     |
| Changes               | +0.3421 / +0.1029 / −0.0749 / −0.3700              |
| Weights sum           | 1.0000, none negative                              |
| Max drawdown achieved | **−16.27%**, with every holding at or above its 2% floor |

The 2% floors bind on VEA, which the unconstrained solve drops to zero
(0.5633, 0.3193, 0.1174, 0.0000 at −15.66%). Pinning VEA to 0.02 and
redistributing the difference costs +0.61 percentage points of
drawdown — a bound always costs something against the objective it constrains.

## Why this one needs extra scrutiny

Drawdown depends on the **order** of returns, not just their distribution, so unlike
volatility it is not a function of the covariance matrix and it is not smooth. A gradient
solver therefore carries no theoretical guarantee of finding the optimum. Verified
empirically instead:

- **Matches `differential_evolution`**, a global optimiser, across 2-, 3-, 4- and
  5-holding requests — gaps of 0.0000% to 0.0050%.
- **Stable across 8 random starting points** — spread 0.0002%.
- Costs ~35 ms and ~295 objective evaluations, roughly twenty times `min_volatility`,
  because every evaluation compounds an equity curve across the whole window.

If the data set changes materially, re-run that comparison rather than assuming it holds.

## Notes

- **Weight bounds are honoured**, applied by clamping after the solve, as in
  `min_volatility`. `equal_weighted` and `risk_parity` ignore them.
- **GLD earns a large weight (31.9%)** despite being the second-most volatile holding.
  Drawdown rewards assets that fall at different times from the rest, and gold's crises
  have rarely coincided with equity crises — an effect volatility alone does not capture.
