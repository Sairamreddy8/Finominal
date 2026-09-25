# Finominal — Portfolio Optimization API

A REST API that takes a portfolio of securities and returns an optimized allocation,
using historical fund returns. Five optimization strategies are available, with optional
per-security weight bounds and a portfolio-level dividend-yield floor.

- **[tests/](tests/)** — a worked request and response for every strategy

## Setup

Requires **Python 3.10+** (developed on 3.12).

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
```

## Run

```bash
python -m uvicorn main:app --reload --reload-dir . --reload-exclude '.venv/*'
```

Or without auto-reload:

```bash
python -m uvicorn main:app
```

The API is then at <http://127.0.0.1:8000>, with interactive docs at
<http://127.0.0.1:8000/docs>.

> **Keep the reload flags scoped.** A bare `--reload` watches the whole directory,
> including `.venv` and its thousands of dependency files. The watcher reads those as
> constant changes and restarts the server in a loop, so it never stays up long enough to
> answer a request.

## Quick check

```bash
curl -s -X POST localhost:8000/ \
  -H 'Content-Type: application/json' \
  -d '{
    "holdings": [
      {"ticker": "AGG", "security_name": "iShares Core US Aggregate Bond ETF", "percentage": 0.3},
      {"ticker": "GLD", "security_name": "SPDR Gold Shares", "percentage": 0.3},
      {"ticker": "SPY", "security_name": "State Street SPDR S&P 500 ETF Trust", "percentage": 0.4}
    ],
    "optimization_objective": "risk_parity"
  }'
```

```json
{
  "optimization_strategy": "risk_parity",
  "allocation_changes": [
    {"ticker": "AGG", "security_name": "iShares Core US Aggregate Bond ETF",
     "current_weight": 0.3, "optimized_weight": 0.6361, "change": 0.3361},
    {"ticker": "GLD", "security_name": "SPDR Gold Shares",
     "current_weight": 0.3, "optimized_weight": 0.1771, "change": -0.1229},
    {"ticker": "SPY", "security_name": "State Street SPDR S&P 500 ETF Trust",
     "current_weight": 0.4, "optimized_weight": 0.1867, "change": -0.2133}
  ]
}
```

Every file in `tests/` holds a complete request you can paste in the same way.

## The endpoint

`POST /` — optimize a portfolio. (`GET /` returns a hello message.)

### Request

| Field | Required | Description |
| --- | --- | --- |
| `holdings[]` | yes | The current portfolio; at least one entry |
| `holdings[].ticker` | yes | One of `AGG`, `GLD`, `IEFA`, `SPY`, `VEA` |
| `holdings[].security_name` | yes | Display name, echoed back in the response |
| `holdings[].percentage` | yes | Current weight as a fraction; all must sum to 1.0 |
| `holdings[].min_weight` | no (0) | Lowest acceptable weight, as a fraction |
| `holdings[].max_weight` | no (1) | Highest acceptable weight, as a fraction |
| `optimization_objective` | yes | One of the five strategies below |
| `min_dividend_yield` | no | Portfolio yield floor as a fraction; `sharpe_ratio` only |

There is no date range in the request. The measurement window is derived from the
holdings — see Conventions. Unrecognised keys (`start_date`, `country_code`,
`rebalance_frequency`) are ignored rather than rejected, so payloads written for the
reference API still work.

### Strategies

| `optimization_objective` | What it optimizes | Respects weight bounds |
| --- | --- | --- |
| `equal_weighted` | Nothing — assigns 1/N | no, by definition |
| `min_volatility` | Lowest portfolio volatility | yes |
| `risk_parity` | Equal risk contribution per holding | no, by definition |
| `min_drawdown` | Shallowest worst-case historical fall | yes |
| `sharpe_ratio` | Highest return per unit of risk | yes |

`equal_weighted` and `risk_parity` ignore `min_weight` / `max_weight` because box
constraints contradict what those strategies mean — an equal split is equal, and equal
risk contribution is equal. The bounds are still accepted and validated.

The other three apply them differently. `min_volatility` and `min_drawdown` solve
unconstrained, then pin any out-of-range weight to the bound it breached and redistribute
the difference so the book still totals 100%. `sharpe_ratio` passes its bounds to the
solver directly, because it can also carry a dividend-yield floor and clamping after the
solve could drag the yield back below it.

### Response

```json
{
  "optimization_strategy": "<the strategy applied>",
  "allocation_changes": [
    {"ticker": "...", "security_name": "...",
     "current_weight": 0.3, "optimized_weight": 0.6361, "change": 0.3361}
  ]
}
```

`change` is `optimized_weight − current_weight`. All weights are fractions rounded to four
decimals.

### Errors

| Condition | Status |
| --- | --- |
| Ticker not in the data set | 400 |
| Malformed body, weights not summing to 1.0, `min_weight` > `max_weight`, unknown strategy | 422 |
| Weight bounds no portfolio can satisfy | 422 |
| `min_dividend_yield` above what any allocation can reach | 422 |
| Too little overlapping history (under 60 days) | 422 |

## Conventions

- **Everything is a fraction, never a percentage.** `0.3` means 30%, `min_dividend_yield`
  `0.025` means 2.5%. One rule for the whole payload.
- **Weights must sum to 1.0** on input (tolerance 1e-9), and always do on output.
- **No short selling** — every weight is between 0 and 1.
- **The measurement window comes from your holdings, not your request.** Metrics are
  computed over the longest period all requested securities have data for. Asking for
  SPY + AGG reaches back to 2003; adding IEFA moves the start to 2012 and changes every
  resulting number. The request has no date range, because nothing could honour one.
- **Annualization uses 252 trading days.**
- **The risk-free rate is 0%**, since the data contains no cash series. Sharpe is
  therefore return-per-unit-risk, not a true excess-return Sharpe, and is not comparable
  to figures published elsewhere.

## Data

Three CSVs in `data/`, parsed once at startup and cached:

| File | Contents |
| --- | --- |
| `Data.xlsx - Fund Returns.csv` | Daily total returns for the five funds |
| `Data.xlsx - Fund Info.csv` | Fund names and dividend yields |
| `Data.xlsx - Factor Returns.csv` | Momentum, Size and Value factors — loaded, not yet used |

Returns are stored as percentage strings (`"0.08%"`) and converted to fractions on load.
GLD has no dividend yield and is treated as 0%, which is correct for gold rather than
missing data. Point `FINOMINAL_DATA_DIR` at another directory to use a different data set;
files are located by filename suffix, not by their full names.

Fund inception dates differ, which is what drives the window behaviour above:

| | Data from |
| --- | --- |
| SPY | 1993-01-29 |
| AGG | 2003-09-26 |
| GLD | 2004-11-18 |
| VEA | 2007-07-26 |
| IEFA | 2012-10-23 |

All five series end 2026-05-27.

## Layout

```
main.py             FastAPI app: routes and error handlers
utils/
  config.py         conventions: 252 trading days, risk-free rate, data directory
  schemas.py        request and response models, and all validation
  market_data.py    CSV loading, and resolving the common window for a set of holdings
  metrics.py        CAGR, volatility, drawdown, Sharpe and the rest
  optimizer.py      the five strategies, the solver, and response assembly
data/               the three CSV files
tests/              a worked request and response per strategy
```

Dependencies point one way: `main` → `optimizer` → `metrics` / `market_data` → `config`.
`metrics.py` and `market_data.py` import no pydantic and no FastAPI, so they can be used
directly for analysis.

**To add a strategy**: write a function in `utils/optimizer.py` taking
`(returns, bounds, request)` and returning weights, add a member to
`OptimizationObjective` in `utils/schemas.py`, and register it in `STRATEGIES`. An import
time assertion fails loudly if an objective is advertised with no implementation behind
it.
