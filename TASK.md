# Your Task

Build a REST API with an endpoint that accepts:
A list of securities (tickers) with their return data
An optimization strategy name
Optional constraints (e.g., min/max weights per security and portfolio-level constraints such as Min CAGR, Volatility Range, Max Drawdown, and Min Dividend Yield)
The API must return:
Optimized portfolio weights for each security (the Allocation Changes section)
(Bonus) Factor betas for both the current and optimized portfolio

# Optimization strategy to implement

1. Equal Weights: Assign equal allocation to all securities. Simple baseline — sum of weights must equal 100%.

# Technical Requirements

Language & Framework
You may use any Python language framework (Django, FastAPI, Flask etc)
The API must be runnable locally — provide clear setup instructions

Code Quality
Clean, readable, and well-commented code
Proper error handling (invalid tickers, missing data, unsupported strategy)
A README.md explaining how to set up and run the project
Unit tests are a bonus but not required

# Constraints

Weights must always sum to 100%
No individual weight may be negative (no short selling)
If min/max weight constraints are passed in the request, they must be respected
• If portfolio-level constraints are passed in the request, they must be respected where feasible

# Example

Payload:

```json
{
  "holdings": [
    {
      "ticker": "AGG",
      "security_name": "iShares Core US Aggregate Bond ETF",
      "percentage": 0.3,
      "min_weight": 0,
      "max_weight": 1
    },
    {
      "ticker": "GLD",
      "security_name": "SPDR Gold Shares",
      "percentage": 0.3,
      "min_weight": 0,
      "max_weight": 1
    },
    {
      "ticker": "SPY",
      "security_name": "State Street SPDR S&P 500 ETF Trust",
      "percentage": 0.4,
      "min_weight": 0,
      "max_weight": 1
    }
  ],
  "optimization_objective": "equal_weighted",
  "start_date": "2004-11-18",
  "end_date": "2026-09-22",
  "country_code": "US",
  "rebalance_frequency": "Y"
}
```

Response:

```json
{
  "success": true,
  "data": {
    "benchmarkNames": {
      "equity": "S&P 500",
      "bond": "Bloomberg Barclays US Aggregate Bond Index",
      "commodity": "Dow Jones Commodity Index",
      "currency": "US Dollar Index"
    },
    "lookbackYears": 21.8,
    "optimizedPortfolio": [
      {
        "ticker": "AGG",
        "name": "iShares Core US Aggregate Bond ETF",
        "optimizedWeight": 0.3333,
        "currentWeight": 0.3,
        "change": 0.0333
      },
      {
        "ticker": "GLD",
        "name": "SPDR Gold Shares",
        "optimizedWeight": 0.3333,
        "currentWeight": 0.3,
        "change": 0.0333
      },
      {
        "ticker": "SPY",
        "name": "State Street SPDR S&P 500 ETF Trust",
        "optimizedWeight": 0.3333,
        "currentWeight": 0.4,
        "change": -0.0667
      }
    ],
    "metrics": {
      "factorBetas": {
        "equityQuality": {
          "initial": 0,
          "optimized": 0,
          "change": 0
        },
        "equityMomentum": {
          "initial": 0.0558,
          "optimized": 0.0563,
          "change": 0.0005
        },
        "equitySize": {
          "initial": 0,
          "optimized": 0,
          "change": 0
        },
        "equityValue": {
          "initial": -0.0697,
          "optimized": -0.0805,
          "change": -0.0108
        },
        "equityVolatility": {
          "initial": 0,
          "optimized": 0,
          "change": 0
        }
      },
      "assetClassBreakdown": {
        "initial": {
          "equityIndex": 0.6393,
          "bondIndex": 0.0004,
          "currency": 0,
          "commodity": 0.3362,
          "equityValue": 0.0024,
          "equitySize": 0.0053,
          "equityMomentum": 0.0013,
          "equityQuality": 0.0012,
          "equityVolatility": 0.0073,
          "equityFactor": 0.0186,
          "others": 0.0055,
          "equityGrowth": 0.0011
        },
        "optimized": {
          "equityIndex": 0.5278,
          "bondIndex": 0.0006,
          "currency": 0,
          "commodity": 0.449,
          "equityValue": 0.0019,
          "equitySize": 0.0046,
          "equityMomentum": 0.0013,
          "equityQuality": 0.0021,
          "equityVolatility": 0.0069,
          "equityFactor": 0.0172,
          "others": 0.0054,
          "equityGrowth": 0.0003
        },
        "change": {
          "equityQuality": 0.0009,
          "bondIndex": 0.0002,
          "equityIndex": -0.1115,
          "equityFactor": -0.0014,
          "equitySize": -0.0007,
          "equityValue": -0.0004,
          "equityVolatility": -0.0003,
          "equityGrowth": -0.0009,
          "equityMomentum": 0,
          "others": 0,
          "commodity": 0.1128,
          "currency": 0
        }
      },
      "sectorAllocation": {
        "initial": {
          "Consumer Discretionary": 0.0422,
          "Consumer Staples": 0.0223,
          "Energy": 0.0136,
          "Financials": 0.0353,
          "Health Care": 0.0362,
          "Industrials": 0.0366,
          "Information Technology": 0.1889,
          "Materials": 0.0071,
          "Real Estate": 0.0074,
          "Utilities": 0.0102,
          "Others": 0
        },
        "optimized": {
          "Consumer Discretionary": 0.0351,
          "Consumer Staples": 0.0186,
          "Energy": 0.0113,
          "Financials": 0.0294,
          "Health Care": 0.0302,
          "Industrials": 0.0305,
          "Information Technology": 0.1574,
          "Materials": 0.0059,
          "Real Estate": 0.0062,
          "Utilities": 0.0085,
          "Others": 0
        },
        "change": {
          "Utilities": -0.0017,
          "Others": 0,
          "Information Technology": -0.0315,
          "Consumer Discretionary": -0.007,
          "Real Estate": -0.0012,
          "Energy": -0.0023,
          "Materials": -0.0012,
          "Consumer Staples": -0.0037,
          "Financials": -0.0059,
          "Industrials": -0.0061,
          "Health Care": -0.006
        }
      },
      "optimizationResults": {
        "fees": {
          "initial": 0.0016,
          "optimized": 0.0017,
          "change": 0.0001,
          "benchmark": null
        },
        "cagr": {
          "initial": 0.0945,
          "optimized": 0.0925,
          "change": -0.002,
          "benchmark": null
        },
        "totalReturn": {
          "initial": 6.161,
          "optimized": 5.8752,
          "change": -0.2858,
          "benchmark": null
        },
        "expectedReturn": {
          "initial": 0.0748,
          "optimized": 0.0764,
          "change": 0.0016,
          "benchmark": null
        },
        "volatility": {
          "initial": 0.1106,
          "optimized": 0.1091,
          "change": -0.0015,
          "benchmark": null
        },
        "sharpeRatio": {
          "initial": 0.6857,
          "optimized": 0.6766,
          "change": -0.0091,
          "benchmark": null
        },
        "maxDrawdown": {
          "initial": -0.2514,
          "optimized": -0.2355,
          "change": 0.0159,
          "benchmark": null
        },
        "dividendYield": {
          "initial": 0.0233,
          "optimized": 0.0256,
          "change": 0.0022,
          "benchmark": null
        },
        "trackingError": {
          "initial": 0,
          "optimized": 0,
          "change": 0,
          "benchmark": null
        }
      },
      "marketBreakdown": {
        "initial": {
          "originalCountryPercent": 0.6695,
          "originalEmergingMarketPercent": 0.0019,
          "originalInternationalPercent": 0.0199,
          "other": 0.3087
        },
        "optimized": {
          "originalCountryPercent": 0.6356,
          "originalEmergingMarketPercent": 0.0021,
          "originalInternationalPercent": 0.0193,
          "other": 0.3429
        },
        "change": {
          "other": 0.0343,
          "originalCountryPercent": -0.0339,
          "originalInternationalPercent": -0.0006,
          "originalEmergingMarketPercent": 0.0002
        }
      }
    },
    "efficientFrontierChartData": [
      {
        "name": "100% Equity",
        "cagr": 0.1101,
        "volatility": 0.1884
      },
      {
        "name": "Benchmark US - 80/20 - Aggressive",
        "cagr": 0.0955,
        "volatility": 0.1486
      },
      {
        "name": "Benchmark US - 60/40 - Moderate",
        "cagr": 0.0801,
        "volatility": 0.1118
      },
      {
        "name": "Benchmark US - 40/60 - Conservative",
        "cagr": 0.064,
        "volatility": 0.0792
      },
      {
        "name": "Benchmark US - 20/80 - Defensive",
        "cagr": 0.0471,
        "volatility": 0.0553
      },
      {
        "name": "100% Bond",
        "cagr": 0.0294,
        "volatility": 0.0519
      }
    ]
  }
}
```

