"""Conventions and tunables shared by the data and metrics layers."""

from pathlib import Path

# Directory holding the CSV fixtures. Overridable so a different data set can be used
# without touching code.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Single annualization convention. Daily series are scaled by 252 trading days per year.
TRADING_DAYS = 252

# Risk-free rate used by the Sharpe ratio, as a fraction.
#
# The supplied data contains no T-bill, cash or money-market series, so there is nothing
# to derive a real rate from. Sharpe is therefore expected_return / volatility, NOT a
# true excess-return Sharpe. Document this wherever the figure is published.
RISK_FREE_RATE = 0.0

# A window shorter than this makes the annualized metrics meaningless.
MIN_OBSERVATIONS = 60

# Days per year used to convert a window into a lookback in years.
DAYS_PER_YEAR = 365.25
