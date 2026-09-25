"""Maximum drawdown.

This module holds only what the optimizer needs: `min_drawdown` is the one strategy whose
objective cannot be expressed through the covariance matrix, because drawdown depends on
the order of returns rather than their distribution.

Everything else a portfolio might be measured by - CAGR, volatility, Sharpe - is computed
inline in ``optimizer.py`` where the solver needs it, or not at all. See STRATEGIES.md.

Returns are fractions: 0.0008 means +0.08% that day.
"""

from __future__ import annotations

import numpy as np


def _as_array(returns) -> np.ndarray:
    return np.asarray(returns, dtype=float).ravel()


def equity_curve(returns) -> np.ndarray:
    """Growth of one unit invested, compounded daily."""
    return np.cumprod(1.0 + _as_array(returns))


def max_drawdown(returns) -> float:
    """Largest peak-to-trough decline, as a positive fraction.

    ``np.maximum.accumulate`` gives the running high-water mark; dividing the curve by it
    shows how far below the peak each day sat. A return of 0.22 means the series fell 22%
    below its previous high at the worst point.
    """
    daily = _as_array(returns)
    if daily.size == 0:
        return 0.0
    curve = equity_curve(daily)
    return float(np.max(1.0 - curve / np.maximum.accumulate(curve)))
