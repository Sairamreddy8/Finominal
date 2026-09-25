# Test — `risk_parity`

Two holdings with very different volatilities — a bond fund and an equity fund — which
is the clearest setting in which to see what risk parity actually does.

## Request

```json
{
  "holdings": [
    {
      "ticker": "AGG",
      "security_name": "iShares Core US Aggregate Bond ETF",
      "percentage": 0.75,
      "min_weight": 0,
      "max_weight": 1
    },
    {
      "ticker": "VEA",
      "security_name": "Vanguard FTSE Developed Markets ETF",
      "percentage": 0.25,
      "min_weight": 0,
      "max_weight": 1
    }
  ],
  "optimization_objective": "risk_parity"
}
```

## Response

```json
{
  "optimization_strategy": "risk_parity",
  "allocation_changes": [
    {
      "ticker": "AGG",
      "security_name": "iShares Core US Aggregate Bond ETF",
      "current_weight": 0.75,
      "optimized_weight": 0.7987,
      "change": 0.0487
    },
    {
      "ticker": "VEA",
      "security_name": "Vanguard FTSE Developed Markets ETF",
      "current_weight": 0.25,
      "optimized_weight": 0.2013,
      "change": -0.0487
    }
  ]
}
```

## Expected output

| | value |
| --- | --- |
| Weights | AGG 0.7987, VEA 0.2013 |
| Changes | +0.0487 / −0.0487 |
| Weights sum | 1.0000, none negative |
| Risk parity achieved | risk shares 0.5001 / 0.4999 — within 1e-4 of 1/2 |

Risk shares are not returned by the API. They are the property this case exists to
verify, checked directly against `optimizer._risk_shares`.

## What this case shows

AGG's volatility is 5.44%; VEA's is
21.57% — roughly 4.0
times higher. To make the two contribute **equally** to portfolio risk, the calmer fund
must be held in much greater size: **79.9% AGG against 20.1% VEA**.

The starting 75/25 book is already close to that, so the change is small
(+0.0487). Compare what an even 50/50 split would
do to the risk balance:

| | AGG | VEA |
| --- | --- | --- |
| Risk share at 50/50 | 6.8% | 93.2% |
| Risk share at parity | 50.0% | 50.0% |

Half the capital in AGG buys only 6.8% of the risk. That gap is the whole
motivation for the strategy.

Volatility falls 6.89% → 6.26% and the worst drawdown from
-20.96% to -19.57%, at a cost of
0.18 percentage points of CAGR (4.11% → 3.93%).

## Notes

- **`min_weight` / `max_weight` are ignored by this strategy**, by design — clamping the
  weights would break the parity that defines it. This request leaves them at their
  defaults (0 and 1), so nothing would bind in any case.
- **The window is 2007-07-26 → 2026-05-27** (4739 observations,
  18.84 years), bounded by VEA's inception.
