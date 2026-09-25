"""Request and response schemas for the portfolio optimization endpoint.

Field names are snake_case throughout, and a security's name is ``security_name`` on
both the request and the response. TASK.md's payload mixes conventions (companyName,
minWeight, maxWeight in camelCase alongside snake_case start_date); this schema
normalizes all of them, and drops the fields it would never act on.
"""

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class OptimizationObjective(str, Enum):
    """Supported optimization strategies.

    A closed set, so an unrecognised objective is rejected by the schema with the
    valid options listed, rather than reaching the optimizer as an unknown string.
    """

    EQUAL_WEIGHTED = "equal_weighted"
    RISK_PARITY = "risk_parity"
    MIN_VOLATILITY = "min_volatility"
    MIN_DRAWDOWN = "min_drawdown"
    SHARPE_RATIO = "sharpe_ratio"


class Holding(BaseModel):
    """One position in the current portfolio.

    Weights are fractions, not percentages: 0.3 means 30% and max_weight 1 means 100%.
    """

    ticker: str
    security_name: str
    percentage: float = Field(..., ge=0, le=1, description="Current allocation.")
    min_weight: float = Field(0, ge=0, le=1, description="Lowest acceptable weight.")
    max_weight: float = Field(1, ge=0, le=1, description="Highest acceptable weight.")

    @model_validator(mode="after")
    def check_bounds(self):
        if self.min_weight > self.max_weight:
            raise ValueError(
                f"{self.ticker}: min_weight ({self.min_weight}) exceeds "
                f"max_weight ({self.max_weight})"
            )
        return self


class OptimizationRequest(BaseModel):
    """A portfolio and the strategy to apply to it.

    There is deliberately no date range here. The measurement window is derived from the
    holdings - the longest span over which all of them have data - so a caller cannot set
    it, and a field suggesting otherwise would mislead. Unrecognised keys such as
    start_date or country_code are ignored rather than rejected, so payloads written for
    the reference API still work.
    """

    holdings: list[Holding] = Field(..., min_length=1)
    optimization_objective: OptimizationObjective
    min_dividend_yield: float | None = Field(
        None,
        ge=0,
        le=1,
        description=(
            "Portfolio-level floor on weighted dividend yield, as a fraction "
            "(0.025 = 2.5%). Applied by sharpe_ratio only."
        ),
    )

    @model_validator(mode="after")
    def check_no_duplicate_tickers(self):
        """Reject a portfolio listing the same security twice.

        Duplicates are not merely redundant: they make the covariance matrix singular,
        and the split between the duplicated entries is arbitrary because the objective
        is flat along that direction. The caller gets a plausible-looking answer to a
        question they did not mean to ask.
        """
        tickers = [h.ticker for h in self.holdings]
        duplicates = sorted({t for t in tickers if tickers.count(t) > 1})
        if duplicates:
            raise ValueError(f"duplicate tickers in holdings: {', '.join(duplicates)}")
        return self

    @model_validator(mode="after")
    def check_allocation(self):
        total = sum(h.percentage for h in self.holdings)
        # abs() matters: `1 - total < 1e-9` is true for every total above 1, so a
        # 300% book would pass. Tolerance absorbs float noise (0.42+0.49+0.09
        # sums to 0.9999999999999999), not genuine mis-allocation.
        if abs(1 - total) > 1e-9:
            raise ValueError(
                f"Allocation weights must sum to 100%, got {total:.4%}"
            )
        return self

class AllocationChange(BaseModel):
    """One holding's move from its current weight to its optimized weight."""

    ticker: str
    security_name: str
    current_weight: float
    optimized_weight: float
    change: float


class OptimizationResponse(BaseModel):
    """The optimized allocation."""

    optimization_strategy: OptimizationObjective
    allocation_changes: list[AllocationChange]
