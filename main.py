"""Minimal FastAPI application."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from utils import market_data
from utils.optimizer import (
    InfeasibleBoundsError,
    OptimizationFailedError,
    UnreachableYieldError,
    optimize,
)
from utils.schemas import OptimizationRequest, OptimizationResponse

app = FastAPI(title="Finominal API")


@app.exception_handler(market_data.UnknownTickerError)
def handle_unknown_ticker(request: Request, exc: market_data.UnknownTickerError):
    """A ticker with no data is a bad request, not a server fault."""
    return JSONResponse(
        status_code=400,
        content={
            "detail": str(exc),
            "unknown_tickers": exc.unknown,
            "known_tickers": exc.known,
        },
    )


@app.exception_handler(market_data.InsufficientHistoryError)
def handle_insufficient_history(
    request: Request, exc: market_data.InsufficientHistoryError
):
    """The request is well-formed but cannot be answered meaningfully."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": str(exc),
            "observations": exc.observations,
            "required_observations": exc.required,
            "limiting_ticker": exc.limiting_ticker,
        },
    )


@app.exception_handler(InfeasibleBoundsError)
def handle_infeasible_bounds(request: Request, exc: InfeasibleBoundsError):
    """The weight bounds rule out every allocation that totals 100%."""
    return JSONResponse(
        status_code=422,
        content={"detail": f"Infeasible weight bounds: {exc}"},
    )


@app.exception_handler(UnreachableYieldError)
def handle_unreachable_yield(request: Request, exc: UnreachableYieldError):
    """No allocation of these holdings can reach the requested dividend yield."""
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(OptimizationFailedError)
def handle_optimization_failed(request: Request, exc: OptimizationFailedError):
    """Well-formed request, but the solver could not converge on this data."""
    return JSONResponse(
        status_code=422,
        content={"detail": f"Optimization failed to converge: {exc}"},
    )


@app.get("/")
def read_root():
    return {"message": "Hello World"}


@app.post("/", response_model=OptimizationResponse)
def optimize_portfolio(request: OptimizationRequest):
    """Optimize the portfolio and report each holding's weight change."""
    return optimize(request)
