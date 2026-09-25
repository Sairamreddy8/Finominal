# Metrics and Strategies

Everything here is explained as **code you can run**, not formula notation. Open a Python
shell in the project root and follow along:

```python
import numpy as np
np.set_printoptions(precision=4, suppress=True)   # so arrays print as shown below

from utils import market_data as md, metrics, optimizer
aligned, window = md.common_window(["AGG", "GLD", "SPY"])
R = aligned.to_numpy(dtype=float)     # (5413 days, 3 funds)
```

`R` is the only input any of this needs: one row per trading day, one column per fund,
each cell that day's return as a fraction (`0.0008` = +0.08%).

---

# Which metrics the optimizer actually needs

Short answer: **almost none of them.**

`utils/metrics.py` used to define nine functions. Tracing a real request showed only
**one** was ever called, so the rest were removed — the module now holds `equity_curve`
and `max_drawdown` and nothing else.

| Request | Functions called from `metrics.py` |
| --- | --- |
| `equal_weighted` | none |
| `min_volatility` | none |
| `risk_parity` | none |
| `min_drawdown` | `max_drawdown` (275×), and `equity_curve` inside it |
| `sharpe_ratio` | none |

That is not because the other strategies need no maths — it is because **their maths is
written inline in `optimizer.py`**, in terms the solver can differentiate, rather than
going through `metrics.py`.

## What each strategy genuinely requires

| Strategy | Needs | Where that code lives |
| --- | --- | --- |
| `equal_weighted` | nothing | `np.full(n, 1/n)` |
| `min_volatility` | covariance matrix | `optimizer._covariance` |
| `risk_parity` | covariance matrix | `optimizer._covariance`, `optimizer._risk_shares` |
| `min_drawdown` | max drawdown | **`metrics.max_drawdown`** |
| `sharpe_ratio` | covariance, mean returns, dividend yields | `optimizer._covariance`, one inline `.mean()`, `market_data.dividend_yield` |

So the genuinely **required** building blocks are:

1. **The covariance matrix** — three of five strategies
2. **Mean returns** — `sharpe_ratio` only
3. **Max drawdown** — `min_drawdown` only
4. **Dividend yields** — `sharpe_ratio`'s optional yield floor only

## What is not required

`cagr`, `cumulative_return`, `expected_return`, `volatility`, `sharpe_ratio`, `compute`,
`portfolio_returns` and the `TickerMetrics` dataclass have all been **deleted**, along
with `market_data.known_tickers` and `market_data.fund_name`. No strategy called any of
them.

They described a portfolio rather than optimizing one. The maths the solver genuinely
needs is written inline in `optimizer.py`, in a form it can differentiate:

```python
expected = returns.mean(axis=0) * TRADING_DAYS   # optimizer.sharpe_ratio
volatility = np.sqrt(w @ cov @ w)                # inside the objective
```

The examples below therefore compute each measure with plain numpy, the same arithmetic
the deleted functions performed. Paste them into a shell to follow along — none of them
depends on code that no longer exists.

---

# Part 1 — The metrics, in code

## Daily returns, and the window

```python
>>> aligned, window = md.common_window(["AGG", "GLD", "SPY"])
>>> window.start, window.end, window.observations, window.lookback_years
(datetime.date(2004, 11, 18), datetime.date(2026, 5, 27), 5413, 21.52)
>>> window.limiting_ticker
'GLD'
```

`common_window` does one important thing beyond loading:

```python
aligned = returns.loc[:, tickers].dropna()   # keep only days ALL of them traded
```

The funds started at different times, so the usable window is their intersection. This is
why **changing the holdings changes every number**:

```python
>>> def cagr(series):
...     return np.prod(1 + series) ** (252 / len(series)) - 1
>>> spy_alone = md.common_window(["SPY"])[0].to_numpy().ravel()
>>> round(cagr(spy_alone), 4)                                    # SPY's own history
0.1089
>>> R5 = md.common_window(["AGG", "GLD", "IEFA", "SPY", "VEA"])[0]
>>> round(cagr(R5["SPY"].to_numpy()), 4)                         # same fund, 2012 on
0.1502
```

10.89% and 15.02% for the same fund. Never compare figures from different windows.

## The equity curve

Almost everything below is derived from one line:

```python
def equity_curve(returns):                   # utils/metrics.py
    return np.cumprod(1.0 + returns)
```

`cumprod` is a running product. Growth of one unit, day after day:

```python
>>> r = np.array([0.10, -0.05, 0.08, -0.12, 0.04])
>>> metrics.equity_curve(r)
array([1.1   , 1.045 , 1.1286, 0.9932, 1.0329])
```

Day 2's −5% is taken off **1.10**, not off 1.00 — `1.10 * 0.95 = 1.045`. That compounding
is why the next three metrics differ from each other.

## Total return

The whole period's growth, end to end — the equity curve's last value, minus one:

```python
>>> round(np.prod(1 + r) - 1, 6)
0.032895                              # the 1.032895 above, minus 1
>>> round(np.prod(1 + R[:, 2]) - 1, 4)   # SPY over 21.52 years
8.4305                                # +843%, i.e. multiplied by 9.43
```

## CAGR

Total return is hard to compare across periods, so CAGR restates it as *the constant
annual rate that would have produced the same growth*:

```python
>>> def cagr(series):
...     return np.prod(1 + series) ** (252 / len(series)) - 1
>>> round(cagr(R[:, 2]), 4)
0.1101                                # 11.01% a year turns 1.00 into 9.43 over 21.52y
```

The exponent `252 / len(series)` converts "per observation" to "per year" —
`252 / 5413 = 0.0466`, so raising 9.43 to that power gives the yearly rate.

**CAGR and total return are the same fact.** Given the day count, each determines the
other — the expression above is literally built from `np.prod(1 + series)`, which *is*
total return plus one.

## Expected return

```python
>>> def expected_return(series):
...     return series.mean() * 252
```

The plain average day, scaled up by 252. Note this is **multiplication, not
compounding** — that difference matters below.

```python
>>> round(expected_return(R[:, 2]), 4), round(cagr(R[:, 2]), 4)
(0.1224, 0.1101)                      # SPY: 12.24% vs 11.01%
```

Why the gap? Volatility drag:

```python
>>> round_trip = np.array([0.5, -0.5])
>>> expected_return(round_trip)              # average day is 0%
0.0
>>> np.prod(1 + round_trip) - 1              # but you hold 0.75
-0.25
```

Gain 50%, lose 50%, end down 25%. The drag grows with volatility — compare calm AGG to
jumpy SPY:

```python
>>> for i, t in enumerate(["AGG", "GLD", "SPY"]):
...     print(t, round(expected_return(R[:, i]) - cagr(R[:, i]), 4))
AGG 0.0009      # 0.09 points
GLD 0.011       # 1.10 points
SPY 0.0123      # 1.23 points
```

One caveat the code makes obvious: `expected_return` multiplies by 252 while `cagr`
compounds over 252. For realistic daily moves the drag dominates and expected return is
larger, as above. Push the daily mean past ~0.1% and compounding wins instead. Read the
gap as a signal about volatility, not as a law.

## Volatility

```python
>>> def volatility(series):
...     return series.std(ddof=1) * np.sqrt(252)
```

Standard deviation of daily returns, annualized. Two details:

- `ddof=1` is the *sample* standard deviation — we have a sample of history, not the
  whole population.
- `np.sqrt(252)`, not `252`. Variance adds over time; standard deviation is its square
  root, so a year's worth scales by √252 ≈ 15.87.

```python
>>> [round(volatility(R[:, i]), 4) for i in range(3)]
[0.0521, 0.1813, 0.1892]              # AGG, GLD, SPY
```

**AGG is roughly a third as volatile as the other two.** That single fact drives nearly
every allocation in Part 2.

## The covariance matrix

Volatility describes one fund. Combining funds needs to know whether they fall *together*:

```python
def _covariance(returns):                        # in optimizer.py
    return np.atleast_2d(np.cov(returns, rowvar=False)) * TRADING_DAYS
```

`rowvar=False` says columns are the variables. The result is 3×3 — each fund's variance
on the diagonal, each pair's co-movement off it. A portfolio's variance is then one
expression:

```python
>>> cov = optimizer._covariance(R)
>>> w = np.array([1/3, 1/3, 1/3])
>>> round(w @ cov @ w, 5)             # portfolio variance
0.00882
>>> round(np.sqrt(w @ cov @ w), 4)    # portfolio volatility
0.0939
```

`w @ cov @ w` is the single most important line in this codebase — three of the five
strategies are built on it. Read it as: *for every pair of funds, multiply their two
weights by how much they move together, and add it all up.*

Diversification is the off-diagonal terms doing work:

```python
>>> round(np.mean([volatility(R[:, i]) for i in range(3)]), 4)   # naive average
0.1409
>>> round(volatility(R @ w), 4)                                  # actual portfolio
0.0939
```

14.09% if you just averaged the three; **9.39%** in reality, because they rarely fall at
once:

```python
>>> corr = cov / np.outer(np.sqrt(np.diag(cov)), np.sqrt(np.diag(cov)))
>>> [round(x, 2) for x in (corr[0, 2], corr[1, 2], corr[0, 1])]
[-0.0, 0.06, 0.2]                     # AGG/SPY, GLD/SPY, AGG/GLD
```

**The covariance matrix cannot see the order of returns.** It knows how big moves are and
whether they coincide, never their sequence. That limitation is why the next metric needs
entirely different machinery.

## Maximum drawdown

```python
def max_drawdown(returns):
    curve = equity_curve(returns)
    return float(np.max(1.0 - curve / np.maximum.accumulate(curve)))
```

`np.maximum.accumulate` is a running high-water mark. Dividing the curve by it gives how
far below the peak you were on each day; `1 -` turns that into a fall, and `np.max` takes
the worst:

```python
>>> curve = metrics.equity_curve(r)
>>> curve
array([1.1   , 1.045 , 1.1286, 0.9932, 1.0329])
>>> np.maximum.accumulate(curve)
array([1.1   , 1.1   , 1.1286, 1.1286, 1.1286])
>>> 1 - curve / np.maximum.accumulate(curve)
array([0.    , 0.05  , 0.    , 0.12  , 0.0848])
>>> metrics.max_drawdown(r)
0.12                                  # the worst of those
```

Day 4's 12% is the answer — a bigger fall from a higher peak than day 2's 5%.

**This is the only metric that sees the order of returns.** Shuffle them and watch:

```python
>>> shuffled = np.random.default_rng(0).permutation(spy_alone)
>>> round(cagr(spy_alone), 4), round(cagr(shuffled), 4)
(0.1089, 0.1089)                      # identical
>>> round(volatility(spy_alone), 3), round(volatility(shuffled), 3)
(0.186, 0.186)                        # identical
>>> round(metrics.max_drawdown(spy_alone), 4), round(metrics.max_drawdown(shuffled), 4)
(0.5526, 0.5424)                      # different
```

Same returns, same order-blind metrics, different drawdown — it ranges 38%–54% across
shuffles against the 55% that actually happened. No combination of the others reproduces
it, which is exactly why `min_drawdown` has to compound the curve instead of reading
`cov`.

The API reports it **negative**: `-0.2316` means a 23.16% fall.

## Sharpe ratio

```python
>>> def sharpe(series, risk_free_rate=0.0):
...     return (expected_return(series) - risk_free_rate) / volatility(series)
```

Reward divided by risk, so two portfolios returning 8% can be compared when one swings
twice as hard.

`RISK_FREE_RATE` is **0** (`utils/config.py`), because the data has no cash series. So
this is strictly return-per-unit-risk, not a true excess-return Sharpe, and is not
comparable to figures published elsewhere.

With rf = 0 it carries **no new information** — it is literally two other measures
divided, which is why no function for it survives in the codebase:

```python
>>> round(sharpe(R[:, 2]), 4)
0.6469
>>> round(expected_return(R[:, 2]) / volatility(R[:, 2]), 4)
0.6469                                # the same number
```

## Dividend yield

The one metric not computed from returns at all — it is looked up:

```python
>>> [round(md.dividend_yield(t), 4) for t in ["AGG", "GLD", "SPY", "VEA", "IEFA"]]
[0.0397, 0.0, 0.0099, 0.0203, 0.0328]
```

GLD is 0.0 because gold pays no dividend — a fact, not missing data. A portfolio's yield
is the weighted average, `w @ yields`.

## Which metrics are independent

Four of the seven; the rest are restatements:

| Metric | Independent? | Why not |
| --- | --- | --- |
| Expected return | yes | |
| Volatility | yes | |
| Max drawdown | yes | the only order-dependent one |
| Dividend yield | yes | external data |
| CAGR | no | determined by total return + day count |
| Total return | no | the same fact as CAGR |
| Sharpe | no | exactly `expected_return / volatility` |

---

# Part 2 — The strategies, in code

Every strategy is a function taking the return matrix and returning weights. The common
shape:

```python
def some_strategy(returns, bounds, request):
    n = returns.shape[1]
    if n == 1:
        return np.array([1.0])        # one holding gets everything
    ...
    return weights                    # length n, non-negative, sums to 1
```

Four of the five hand an **objective function** to `_solve`, which wraps SLSQP:

```python
def _solve(objective, n, bounds, extra_constraints=None):
    result = minimize(
        objective,                                    # what to make small
        _feasible_start(bounds),                      # where to start
        method="SLSQP",
        bounds=bounds,                                # per-holding limits
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
                    + list(extra_constraints or []),  # weights must total 1
    )
    ...
```

**SLSQP always minimizes.** To maximize something, hand it the negative — which is why
`sharpe_ratio`'s objective starts with a minus sign.

So each strategy differs in exactly one thing: the `objective` it passes.

## `equal_weighted`

```python
def equal_weighted(returns, bounds, request):
    n = returns.shape[1]
    return np.full(n, 1 / n)
```

No solver, no metrics, no return data — `returns` is used only for its shape. Nothing is
estimated, so nothing can be mis-estimated. That is the point of a baseline.

Its blind spot, shown with `_risk_shares` (defined below):

```python
>>> optimizer._risk_shares(np.full(3, 1/3), cov).round(4)
array([0.0585, 0.4644, 0.4772])       # AGG, GLD, SPY
```

Equal *capital*, wildly unequal *risk*: AGG holds a third of the money and carries 5.8% of
the risk, because its volatility is a third of the others'.

## `min_volatility`

**Objective: one line.**

```python
cov = _covariance(returns)
unconstrained = _solve(lambda w: w @ cov @ w, n, [(WEIGHT_FLOOR, 1.0)] * n)
return _clamp_to_bounds(unconstrained, bounds)
```

`w @ cov @ w` is portfolio *variance*, not volatility. Minimizing either gives the same
weights (square root is monotonic), but variance is smooth and better conditioned for the
solver.

```python
>>> optimizer.min_volatility(R, [(0.0, 1.0)] * 3, req)
array([0.912 , 0.0187, 0.0693])
```

**91% into AGG**, the low-volatility fund. Volatility 9.39% → **5.02%**, but CAGR 9.06% →
3.88% and Sharpe to 0.7851 — *the lowest of the five*. Minimizing risk is not maximizing
risk-adjusted return: the objective is told to make one number small and obeys.

A property worth knowing, which the implementation checks:

```python
>>> w = optimizer.min_volatility(R, [(0.0, 1.0)] * 3, req)
>>> optimizer._risk_shares(w, cov)
array([0.912 , 0.0187, 0.0693])       # identical to the weights
```

At the minimum-variance point, each holding's risk share equals its weight exactly. If
that stops holding, the solver did not converge.

## `risk_parity`

**Objective: make every holding's risk share equal.** First, what a risk share is:

```python
def _risk_shares(weights, cov):
    return weights * (cov @ weights) / (weights @ cov @ weights)
```

Read it as: `cov @ weights` is how much each fund moves with the portfolio;
multiplying by its own weight gives its contribution to portfolio risk; dividing by
total variance turns those into shares that sum to 1.

Then the objective is squared error against the target:

```python
target = 1 / n
_solve(lambda w: ((_risk_shares(w, cov) - target) ** 2).sum(), n, open_bounds)
```

Squaring makes every deviation positive, so the sum is zero only when all shares equal
`1/n` — which is exactly what "equal risk" means.

```python
>>> w = optimizer.risk_parity(R, [(0.0, 1.0)] * 3, req)
>>> w
array([0.6361, 0.1771, 0.1867])
>>> optimizer._risk_shares(w, cov)
array([0.3333, 0.3333, 0.3333])       # the point of the strategy
```

**Why 63.6% in AGG?** Its volatility is 5.21% against ~18% for the others. To make a calm
asset carry a third of the risk you must hold a lot of it. The big weight is a
*consequence* of equalizing risk, not a view on bonds.

## `min_drawdown`

**Objective: the only one that calls `metrics.py`.**

```python
unconstrained = _solve(
    lambda w: metrics.max_drawdown(returns @ w), n, [(WEIGHT_FLOOR, 1.0)] * n
)
return _clamp_to_bounds(unconstrained, bounds)
```

`returns @ w` builds the portfolio's daily series, then `max_drawdown` compounds it into
an equity curve and finds the worst fall. Every other strategy reads a 3×3 matrix; this
one walks 5,413 rows **per evaluation**, and the solver evaluates it 275 times. That makes
it about twenty times slower than `min_volatility`.

It is also **not smooth** — drawdown jumps when the worst trough shifts to a different
date — so a gradient solver has no theoretical guarantee here. Checked empirically rather
than assumed: SLSQP matches `differential_evolution` (a global optimizer) across 2-, 3-,
4- and 5-holding requests, and reaches the same point from eight random starts. Re-run
that comparison if the data changes materially.

```python
>>> optimizer.min_drawdown(R, [(0.0, 1.0)] * 3, req)
array([0.5633, 0.3193, 0.1174])
```

Note **GLD at 31.9%**, nearly double what `min_volatility` gives it, despite gold being
the second-most volatile holding. Drawdown rewards assets that fall at *different times*
from the rest — something volatility alone cannot express.

## `sharpe_ratio`

**Objective: negative Sharpe, because SLSQP minimizes.**

```python
cov = _covariance(returns)
expected = returns.mean(axis=0) * TRADING_DAYS      # annualized mean per fund

def negative_sharpe(w):
    volatility = np.sqrt(w @ cov @ w)
    if volatility <= 0:
        return 0.0
    return -(w @ expected) / volatility             # minus => maximize Sharpe

return _solve(negative_sharpe, n, bounds, constraints)
```

`w @ expected` is the portfolio's expected return; `np.sqrt(w @ cov @ w)` its volatility.
Risk-free rate is 0, so the ratio is just one over the other.

```python
>>> optimizer.sharpe_ratio(R, [(0.0, 1.0)] * 3, req)
array([0.6082, 0.184 , 0.2078])       # Sharpe 1.0208, the best of the five
```

This is the only strategy using **expected returns**, and that is its weakness: mean
returns are far noisier estimates than covariance, so its weights move more when the
window shifts, and it readily drops holdings to zero.

### The dividend-yield floor

The one place a metric becomes a **constraint** rather than an objective:

```python
yields = np.array([market_data.dividend_yield(h.ticker) for h in request.holdings])
constraints.append({"type": "ineq", "fun": lambda w: w @ yields - floor})
```

SLSQP's `"ineq"` means *keep this expression ≥ 0*, so `w @ yields - floor >= 0` is
"portfolio yield must be at least the floor". Given as a **fraction** — `0.03` is 3%.

| `min_dividend_yield` | AGG | GLD | SPY | Yield | Sharpe |
| --- | --- | --- | --- | --- | --- |
| none | 0.6082 | 0.1840 | 0.2078 | 2.62% | 1.0208 |
| 0.030 | 0.7138 | 0.1184 | 0.1678 | 3.00% | 0.9583 |
| 0.0397 | 1.0000 | — | — | 3.97% | 0.5855 |

Below the unconstrained yield it does nothing. Above what any allocation can reach it is
rejected with **HTTP 422**, using a greedy fill to find the true ceiling:

```python
def _max_attainable_yield(yields, bounds):
    weights = low.copy()                       # everyone at their minimum
    budget = 1.0 - low.sum()
    for i in np.argsort(-yields):              # highest-yielding first
        take = min(budget, high[i] - low[i])   # fill to its cap
        weights[i] += take
        budget -= take
    return float(weights @ yields)
```

That is exact for a linear objective under box and sum constraints.

## Weight bounds

```python
bounds = [(h.min_weight, h.max_weight) for h in request.holdings]
weights = strategy(returns, bounds, request)     # each strategy decides what to do
```

| Strategy | Bounds | How |
| --- | --- | --- |
| `equal_weighted` | ignored | an equal split is equal by definition |
| `risk_parity` | ignored | clamping would break the parity that defines it |
| `min_volatility` | applied | `_clamp_to_bounds` after solving |
| `min_drawdown` | applied | `_clamp_to_bounds` after solving |
| `sharpe_ratio` | applied | passed straight to SLSQP |

Clamping keeps in-range weights as calculated, pins the rest, and redistributes:

```python
for _ in range(100):
    w = np.clip(w, low, high)                    # pin anything out of range
    gap = 1.0 - w.sum()                          # pinning broke the 100% total
    if abs(gap) < 1e-12:
        break
    free = (w < high - 1e-12) if gap > 0 else (w > low + 1e-12)
    w[free] += gap * (w[free] / w[free].sum())   # push the difference onto the rest
```

The loop repeats because redistributing can push another holding onto a bound.

> **Why `sharpe_ratio` differs.** It can carry a dividend-yield floor, and clamping
> *after* solving could drag the yield back below it — returning a result that quietly
> violates the request. Its bounds go into the solver so both conditions hold at once.
> Any strategy that gains a portfolio-level constraint needs the same treatment.

## Choosing one

| If you want… | Use | Accept |
| --- | --- | --- |
| A neutral baseline, or no faith in estimates | `equal_weighted` | Risk concentrates in your most volatile holdings |
| The smallest swings | `min_volatility` | Heavy concentration, lowest return |
| Every holding to genuinely matter | `risk_parity` | Large weights in low-volatility assets |
| The mildest worst case | `min_drawdown` | Fitted to one historical path; slowest |
| The best risk-adjusted return | `sharpe_ratio` | Rests on noisy expected returns |

## Caveats

- **All of this is backward-looking.** Measurements of what happened, not forecasts. Past
  covariance is a decent guide to future covariance; past returns much less so.
- **The window comes from your holdings**, not your request. There is no date range in
  the request at all, because nothing could honour one.
- **`min_volatility` is the most estimate-sensitive**: it concentrates exactly where the
  covariance estimate says risk is lowest, so an error there is an error in the weights.
- **`min_drawdown` is fitted to one historical path.** The worst fall that did happen is a
  single sample; this is the most overfit-prone of the five.
- **`sharpe_ratio` rests on expected returns**, the weakest of these estimates. Prefer the
  risk-based strategies when you distrust return forecasts.
- **Sharpe assumes a 0% risk-free rate** and is not comparable to published figures.
