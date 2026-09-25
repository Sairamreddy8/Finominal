"""Loading and aligning the historical fund data.

The CSVs store returns as percentage strings ("0.08%"), use CRLF line endings, and carry
a "Data.xlsx - " filename prefix. All of that is normalized here so callers only ever see
tidy float frames indexed by date.

Funds have staggered inception dates, so a set of tickers is only comparable over the
window where all of them trade. ``common_window`` resolves that window and is the entry
point for everything downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd

from utils.config import DATA_DIR, DAYS_PER_YEAR, MIN_OBSERVATIONS

FUND_RETURNS_SUFFIX = "Fund Returns.csv"
FUND_INFO_SUFFIX = "Fund Info.csv"


class MarketDataError(Exception):
    """Base class for problems sourcing historical data."""


class UnknownTickerError(MarketDataError):
    """A requested ticker has no return history."""

    def __init__(self, unknown: list[str], known: list[str]) -> None:
        super().__init__(
            f"No historical data for: {', '.join(unknown)}. Known tickers: {', '.join(known)}"
        )
        self.unknown = unknown
        self.known = known


class InsufficientHistoryError(MarketDataError):
    """The requested tickers share too little overlapping history to measure."""

    def __init__(self, observations: int, required: int, limiting_ticker: str) -> None:
        super().__init__(
            f"Only {observations} overlapping observations; {required} required. "
            f"{limiting_ticker} has the shortest history."
        )
        self.observations = observations
        self.required = required
        self.limiting_ticker = limiting_ticker


@dataclass(frozen=True)
class Window:
    """The period a set of tickers has in common."""

    start: date
    end: date
    observations: int
    lookback_years: float
    limiting_ticker: str  # the holding whose inception truncated the window


def _resolve(suffix: str, data_dir: Path) -> Path:
    """Find the CSV whose filename ends with ``suffix``.

    Matching on the suffix keeps the "Data.xlsx - " prefix and the spaces in the shipped
    filenames out of the code.
    """
    matches = sorted(p for p in data_dir.glob("*.csv") if p.name.endswith(suffix))
    if not matches:
        raise MarketDataError(f"No CSV ending in {suffix!r} found in {data_dir}")
    return matches[0]


def _parse_percent(series: pd.Series) -> pd.Series:
    """Convert a column of "1.23%" strings into fractions (0.0123).

    Blanks become 0.0 - the only blanks in the data are dividend yields for funds that
    pay none (GLD).
    """
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float)
    cleaned = series.astype(str).str.strip().str.rstrip("%")
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0) / 100.0


@lru_cache(maxsize=1)
def load_returns(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Daily fund returns as a dates x tickers frame. Parsed once per process."""
    raw = pd.read_csv(_resolve(FUND_RETURNS_SUFFIX, data_dir))
    raw["date"] = pd.to_datetime(raw["date"])
    raw["return"] = _parse_percent(raw["total_return"])
    wide = raw.pivot_table(index="date", columns="ticker", values="return")
    wide.columns.name = None
    return wide.sort_index()


@lru_cache(maxsize=1)
def load_fund_info(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Fund names and dividend yields (as fractions), indexed by ticker."""
    raw = pd.read_csv(_resolve(FUND_INFO_SUFFIX, data_dir))
    raw["dividend_yield"] = _parse_percent(raw["dividend_yield"])
    return raw.set_index("ticker")


def dividend_yield(ticker: str) -> float:
    """Stated dividend yield as a fraction; funds paying none report 0.0."""
    info = load_fund_info()
    if ticker not in info.index:
        return 0.0
    return float(info.loc[ticker, "dividend_yield"])


def common_window(tickers: list[str]) -> tuple[pd.DataFrame, Window]:
    """Return series for ``tickers`` over the longest period they all share.

    This is the *maximum* overlapping history - no date filtering is applied. The window
    is a consequence of which tickers are asked for: adding a late-inception fund shortens
    it for every holding, which is why metrics must never be compared across windows.
    """
    if not tickers:
        raise MarketDataError("At least one ticker is required")

    returns = load_returns()
    unknown = [t for t in tickers if t not in returns.columns]
    if unknown:
        raise UnknownTickerError(unknown, sorted(returns.columns))

    # dropna() keeps only dates where every requested ticker traded.
    aligned = returns.loc[:, tickers].dropna()

    # Whichever holding starts latest is what truncated the window.
    limiting = max(tickers, key=lambda t: returns[t].dropna().index.min())

    if len(aligned) < MIN_OBSERVATIONS:
        raise InsufficientHistoryError(len(aligned), MIN_OBSERVATIONS, limiting)

    start, end = aligned.index.min(), aligned.index.max()
    window = Window(
        start=start.date(),
        end=end.date(),
        observations=len(aligned),
        lookback_years=round((end - start).days / DAYS_PER_YEAR, 2),
        limiting_ticker=limiting,
    )
    return aligned, window
