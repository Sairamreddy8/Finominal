"""Optimization strategies and the assembly of the optimization response.

Each strategy takes the requested holdings and returns one weight per holding, as
fractions summing to 1. ``optimize`` dispatches on the requested objective, then measures
both the current and the optimized portfolio over the holdings' shared history.
"""

import warnings

import numpy as np
from scipy.optimize import minimize

from utils import market_data
from utils import metrics
from utils.config import TRADING_DAYS
from utils.schemas import (
    AllocationChange,
    OptimizationObjective,
    OptimizationRequest,
    OptimizationResponse,
)

# Weights and metrics are reported to four decimals, matching the reference response
# (three holdings at 0.3333). Note this is a display rounding: 1/3 has no exact decimal
# form, so three equal weights print as 0.9999 rather than 1.0.
WEIGHT_PRECISION = 4


# SLSQP is given a lower bound just above zero rather than exactly zero: at w_i = 0 the
# risk-contribution gradient is undefined, which stalls the solver.
WEIGHT_FLOOR = 1e-8


class OptimizationFailedError(Exception):
    """The solver could not find an allocation for this covariance structure."""


class InfeasibleBoundsError(Exception):
    """No allocation can satisfy the requested weight bounds and still total 100%."""


class UnreachableYieldError(Exception):
    """No allocation of these holdings can reach the requested dividend yield."""


def _max_attainable_yield(
    yields: np.ndarray, bounds: list[tuple[float, float]]
) -> float:
    """The highest weighted dividend yield these holdings can produce.

    Maximising a linear objective under box bounds and a sum constraint is solved exactly
    by a greedy fill: seat every holding at its minimum, then pour the remaining budget
    into the highest-yielding holdings until each hits its cap.
    """
    low = np.array([lo for lo, _ in bounds], dtype=float)
    high = np.array([hi for _, hi in bounds], dtype=float)
    weights = low.copy()
    budget = 1.0 - low.sum()
    for i in np.argsort(-yields):
        if budget <= 0:
            break
        take = min(budget, high[i] - low[i])
        weights[i] += take
        budget -= take
    return float(weights @ yields)


def _check_feasible(bounds: list[tuple[float, float]]) -> None:
    """Reject bound sets that no portfolio can satisfy, before invoking the solver.

    Weights must total 1, so the minimums cannot sum above 1 and the maximums cannot sum
    below it. Caught here the failure names the problem; left to SLSQP it surfaces as an
    opaque convergence error.
    """
    low = sum(lo for lo, _ in bounds)
    high = sum(hi for _, hi in bounds)
    if low > 1.0:
        raise InfeasibleBoundsError(
            f"min_weight values sum to {low:.4f}; they cannot exceed 1.0"
        )
    if high < 1.0:
        raise InfeasibleBoundsError(
            f"max_weight values sum to {high:.4f}; they cannot be below 1.0"
        )


def _clamp_to_bounds(
    weights: np.ndarray, bounds: list[tuple[float, float]]
) -> np.ndarray:
    """Pull an unconstrained allocation inside ``bounds`` while keeping it fully invested.

    A weight already within its bounds is preserved; one outside is pinned to the bound
    it breached. Pinning alone breaks the 100% total, so the shortfall or excess is then
    redistributed across the holdings still free to move, in proportion to their weight.
    Clamping can push a previously free holding onto a bound, so this repeats until the
    weights settle.
    """
    low = np.array([lo for lo, _ in bounds], dtype=float)
    high = np.array([hi for _, hi in bounds], dtype=float)
    w = weights.copy()

    for _ in range(100):
        w = np.clip(w, low, high)
        gap = 1.0 - w.sum()
        if abs(gap) < 1e-12:
            break
        # Only holdings with room to move in the required direction can absorb the gap.
        free = (w < high - 1e-12) if gap > 0 else (w > low + 1e-12)
        if not free.any():
            break
        share = w[free]
        w[free] += gap * (
            share / share.sum() if share.sum() > 0 else np.full(free.sum(), 1 / free.sum())
        )

    return np.clip(w, low, high)


def _feasible_start(bounds: list[tuple[float, float]]) -> np.ndarray:
    """A starting point inside the bounds that already sums to 1.

    Handing SLSQP an infeasible x0 (a flat 1/N can violate tight bounds) makes it work to
    reach feasibility before it optimises, and sometimes fail outright. Distributing the
    slack above the minimums in proportion to each holding's range avoids that.
    """
    low = np.array([lo for lo, _ in bounds], dtype=float)
    span = np.array([hi - lo for lo, hi in bounds], dtype=float)
    if span.sum() <= 0:
        return low
    return low + (1.0 - low.sum()) * span / span.sum()


def _covariance(returns: np.ndarray) -> np.ndarray:
    """Annualized covariance matrix of the holdings.

    atleast_2d keeps a single holding as a (1, 1) matrix rather than a bare scalar.
    """
    return np.atleast_2d(np.cov(returns, rowvar=False)) * TRADING_DAYS


def _risk_shares(weights: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Each holding's share of total portfolio risk, summing to 1.

    Asset i contributes w_i * (cov @ w)_i / sigma_p to portfolio volatility; dividing by
    sigma_p again expresses that as a fraction of the whole.
    """
    return weights * (cov @ weights) / (weights @ cov @ weights)


def _solve(
    objective,
    n: int,
    bounds: list[tuple[float, float]],
    extra_constraints: list[dict] | None = None,
) -> np.ndarray:
    """Minimize ``objective`` over weights that sum to 1 and respect ``bounds``.

    ``extra_constraints`` adds portfolio-level conditions in SLSQP's own format, for
    strategies that must satisfy something beyond the weights themselves.
    """
    with warnings.catch_warnings():
        # SLSQP's line search probes marginally outside the bounds on some problems and
        # warns as it clips back. The converged result still satisfies the bounds and the
        # sum constraint, so this is noise that would otherwise appear in request logs.
        # Correctness is guarded by checking the solution itself, not by this warning.
        warnings.filterwarnings(
            "ignore",
            message="Values in x were outside bounds",
            category=RuntimeWarning,
        )
        result = minimize(
            objective,
            _feasible_start(bounds),
            method="SLSQP",
            bounds=bounds,
            constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
            + list(extra_constraints or []),
            options={"maxiter": 1000, "ftol": 1e-12},
        )
    if not result.success:
        raise OptimizationFailedError(result.message)
    # Renormalise: SLSQP satisfies the sum constraint to tolerance, not exactly.
    weights = np.clip(result.x, 0.0, 1.0)
    return weights / weights.sum()



def equal_weighted(returns: np.ndarray, bounds, request) -> np.ndarray:
    """Assign the same weight to every holding.

    With N holdings each gets 1/N, so the weights sum to 100% by construction and none
    can be negative. Uses no return data at all - note that equal *capital* is not equal
    *risk*: see risk_parity.

    ``bounds`` is accepted for signature symmetry and ignored: min_weight / max_weight
    cannot be honoured by a strategy whose entire definition is an equal split.
    """
    n = returns.shape[1]
    return np.full(n, 1 / n)


def min_volatility(returns: np.ndarray, bounds, request) -> np.ndarray:
    """Find the allocation with the lowest portfolio volatility.

    Minimizes variance rather than standard deviation: the two have the same minimizer
    (sqrt is monotonic) but variance is smooth and better conditioned for the solver.

    This is the one strategy that honours the holdings' min_weight / max_weight. The
    lowest-volatility allocation is found first, then clamped into the requested bounds:
    a weight already inside its range is kept as calculated, one outside is pinned to the
    bound it breached, and the difference is redistributed so the book still totals 100%.

    Left unbounded it concentrates heavily in the lowest-volatility holding, which is
    usually why bounds are supplied.
    """
    n = returns.shape[1]
    if n == 1:
        return np.array([1.0])
    _check_feasible(bounds)
    cov = _covariance(returns)
    # Solve unconstrained, then bring the answer inside the requested bounds. Weights
    # already within their bounds are preserved; the rest are pinned and the difference
    # redistributed, so the book still totals 100%.
    unconstrained = _solve(lambda w: w @ cov @ w, n, [(WEIGHT_FLOOR, 1.0)] * n)
    return _clamp_to_bounds(unconstrained, bounds)


def risk_parity(returns: np.ndarray, bounds, request) -> np.ndarray:
    """Allocate so every holding contributes equally to total portfolio risk.

    Low-volatility assets take a larger share of capital precisely because they add less
    risk per unit invested, which is what separates this from equal weighting.

    A request's min_weight / max_weight are deliberately discarded: the allocation is
    whatever equalises risk contribution, and clamping it would break the parity that is
    the whole point. The bounds used below are wide open, and exist only to keep the
    solver's search inside [0, 1] - the floor avoids an undefined gradient at w_i = 0.
    """
    n = returns.shape[1]
    if n == 1:
        return np.array([1.0])
    cov = _covariance(returns)
    target = 1 / n
    open_bounds = [(WEIGHT_FLOOR, 1.0)] * n
    return _solve(
        lambda w: ((_risk_shares(w, cov) - target) ** 2).sum(), n, open_bounds
    )


def min_drawdown(returns: np.ndarray, bounds, request) -> np.ndarray:
    """Find the allocation whose worst peak-to-trough fall is smallest.

    Unlike volatility, drawdown depends on the *order* of returns, so it is not a
    function of the covariance matrix and cannot be derived from one. The objective is
    evaluated by compounding the portfolio's equity curve directly, which makes it the
    most expensive strategy here - roughly twenty times min_volatility.

    Drawdown is also non-smooth, so a gradient solver carries no theoretical guarantee.
    In practice SLSQP matches a global optimiser on this data and converges to the same
    point from every starting guess; see STRATEGIES.md.

    Bounds are applied afterwards by clamping, as in min_volatility.
    """
    n = returns.shape[1]
    if n == 1:
        return np.array([1.0])
    _check_feasible(bounds)
    unconstrained = _solve(
        lambda w: metrics.max_drawdown(returns @ w), n, [(WEIGHT_FLOOR, 1.0)] * n
    )
    return _clamp_to_bounds(unconstrained, bounds)


def sharpe_ratio(returns: np.ndarray, bounds, request) -> np.ndarray:
    """Find the allocation with the highest return per unit of risk.

    With the risk-free rate at 0 (see config.RISK_FREE_RATE), the Sharpe ratio is the
    annualized mean return over annualized volatility. SLSQP minimizes, so the objective
    is its negative.

    This strategy applies ``min_weight`` / ``max_weight`` **inside** the solver rather
    than clamping afterwards, unlike min_volatility and min_drawdown. It has to: it can
    also carry a portfolio-level floor on dividend yield, and clamping weights after the
    fact could drag the yield back below that floor, returning a result that quietly
    violates the request.
    """
    n = returns.shape[1]
    if n == 1:
        return np.array([1.0])
    _check_feasible(bounds)

    cov = _covariance(returns)
    # Arithmetic mean, annualized - the expected return of the constituents.
    expected = returns.mean(axis=0) * TRADING_DAYS

    constraints = []
    floor = getattr(request, "min_dividend_yield", None)
    if floor is not None:
        yields = np.array(
            [market_data.dividend_yield(h.ticker) for h in request.holdings]
        )
        ceiling = _max_attainable_yield(yields, bounds)
        if floor > ceiling + 1e-12:
            raise UnreachableYieldError(
                f"min_dividend_yield {floor:.2%} is unreachable; the highest attainable "
                f"with these holdings is {ceiling:.2%}"
            )
        constraints.append(
            {"type": "ineq", "fun": lambda w, y=yields, f=floor: w @ y - f}
        )

    def negative_sharpe(w: np.ndarray) -> float:
        volatility = np.sqrt(w @ cov @ w)
        if volatility <= 0:
            return 0.0
        return -(w @ expected) / volatility

    return _solve(negative_sharpe, n, bounds, constraints)

# Registry of objective -> strategy.
STRATEGIES = {
    OptimizationObjective.EQUAL_WEIGHTED: equal_weighted,
    OptimizationObjective.RISK_PARITY: risk_parity,
    OptimizationObjective.MIN_VOLATILITY: min_volatility,
    OptimizationObjective.MIN_DRAWDOWN: min_drawdown,
    OptimizationObjective.SHARPE_RATIO: sharpe_ratio,
}

# Every objective the API advertises must have an implementation behind it. Without this
# check, adding an enum member and forgetting the strategy fails at request time with a
# KeyError (HTTP 500) instead of at import.
_missing = set(OptimizationObjective) - set(STRATEGIES)
assert not _missing, f"OptimizationObjective members with no strategy: {_missing}"


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, WEIGHT_PRECISION)


def optimize(request: OptimizationRequest) -> OptimizationResponse:
    """Run the requested strategy and report each holding's weight change."""
    tickers = [h.ticker for h in request.holdings]

    # The solver-based strategies need the return history, so the window is resolved
    # before dispatch. This is also what rejects unknown tickers.
    aligned, _ = market_data.common_window(tickers)

    # Column order carries the weights: if aligned's columns ever stopped matching the
    # requested order, every allocation below would be silently wrong rather than failing.
    assert list(aligned.columns) == tickers, "return matrix columns must match holdings"

    returns = aligned.to_numpy(dtype=float)

    # The holdings' bounds go to every strategy; each decides what to do with them.
    # min_volatility honours them. equal_weighted and risk_parity discard them, because
    # box constraints would contradict what those strategies mean.
    bounds = [(h.min_weight, h.max_weight) for h in request.holdings]
    strategy = STRATEGIES[request.optimization_objective]
    weights = strategy(returns, bounds, request)

    return OptimizationResponse(
        optimization_strategy=request.optimization_objective,
        allocation_changes=[
            AllocationChange(
                ticker=holding.ticker,
                security_name=holding.security_name,
                current_weight=_round(holding.percentage),
                optimized_weight=_round(weight),
                change=_round(weight - holding.percentage),
            )
            for holding, weight in zip(request.holdings, weights)
        ],
    )
