You are a financial analyst writing a short, factual brief for a demonstration
of Forge in an AI pipeline.  It is not investment advice: give no recommendation,
price target or forecast.

COMPANY: NVDA
PERIOD: Q2 FY2027

EXTRACTED DATA (from public filings):
{
  "company": "NVIDIA Corporation",
  "ticker": "NVDA",
  "period": "Q2 FY2027",
  "currency": "USD",
  "revenue": 96221,
  "cost_of_revenue": 24079,
  "gross_profit": 72142,
  "operating_expenses": 8408,
  "operating_income": 63734,
  "net_income": 59688,
  "eps": 2.46,
  "shares_outstanding": 24285,
  "input": {
    "path": "inputs/NVDA/FY2027-Q2",
    "period": "FY2027-Q2",
    "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000073/q2fy27pr.htm",
    "expected_checked_by_person": true,
    "expected_mismatches": []
  }
}

FORGE CALCULATION RESULTS (deterministic -- these are the authoritative numbers):
{
  "inputs.cost_of_revenue": 24079.0,
  "inputs.net_income": 59688.0,
  "inputs.operating_expenses": 8408.0,
  "inputs.revenue": 96221.0,
  "outputs.gross_margin": 0.749753172384407,
  "outputs.gross_profit": 72142.0,
  "outputs.net_margin": 0.620321967138151,
  "outputs.operating_income": 63734.0,
  "outputs.operating_margin": 0.662371000093535
}

RISK ANALYSIS (Monte Carlo + Sensitivity):
{
  "monte_carlo": {
    "output": "outputs.operating_income",
    "iterations": 10000,
    "mean": 63734.011285795,
    "std_dev": 9952.32791099714,
    "p10": 50781.8804187276,
    "p50": 63723.9179473291,
    "p90": 76416.458805981
  },
  "tornado": {
    "output": "outputs.operating_income",
    "base_value": 63734.0,
    "bars": [
      {
        "input_name": "inputs.revenue",
        "output_at_low": 54111.9,
        "output_at_high": 73356.1,
        "swing": 19244.2,
        "abs_swing": 19244.2,
        "input_low": 86598.9,
        "input_high": 105843.1
      },
      {
        "input_name": "inputs.cost_of_revenue",
        "output_at_low": 66141.9,
        "output_at_high": 61326.1,
        "swing": -4815.79999999999,
        "abs_swing": 4815.79999999999,
        "input_low": 21671.1,
        "input_high": 26486.9
      },
      {
        "input_name": "inputs.operating_expenses",
        "output_at_low": 64574.8,
        "output_at_high": 62893.2,
        "swing": -1681.60000000001,
        "abs_swing": 1681.60000000001,
        "input_low": 7567.2,
        "input_high": 9248.8
      },
      {
        "input_name": "inputs.net_income",
        "output_at_low": 63734.0,
        "output_at_high": 63734.0,
        "swing": 0.0,
        "abs_swing": 0.0,
        "input_low": 53719.2,
        "input_high": 65656.8
      }
    ],
    "total_variance": 25741.6
  },
  "break_even": {
    "vary": "inputs.revenue",
    "target": "outputs.operating_income",
    "target_value": 0.0,
    "solution": 32486.9999837279,
    "achieved": -1.62721225933637e-05,
    "error": 1.62721225933637e-05,
    "iterations": 36,
    "converged": true
  },
  "assumptions": "Each numeric input varied by 10% (tornado: low/high; Monte Carlo: normal with std dev 10% of the value, independent draws)."
}

SCENARIO ANALYSIS (Bull / Base / Bear):
{
  "scenarios": [
    {
      "name": "base",
      "probability": 0.5,
      "revenue": 96221.0,
      "operating_income": 63734.0,
      "scalars": {
        "inputs.cost_of_revenue": 24079.0,
        "inputs.net_income": 59688.0,
        "inputs.operating_expenses": 8408.0,
        "inputs.revenue": 96221.0,
        "outputs.gross_margin": 0.749753172384407,
        "outputs.gross_profit": 72142.0,
        "outputs.net_margin": 0.620321967138151,
        "outputs.operating_income": 63734.0,
        "outputs.operating_margin": 0.662371000093535
      }
    },
    {
      "name": "bear",
      "probability": 0.25,
      "revenue": 86598.9,
      "operating_income": 56519.8,
      "scalars": {
        "inputs.cost_of_revenue": 21671.1,
        "inputs.net_income": 53719.2,
        "inputs.operating_expenses": 8408.0,
        "inputs.revenue": 86598.9,
        "outputs.gross_margin": 0.749753172384407,
        "outputs.gross_profit": 64927.8,
        "outputs.net_margin": 0.620321967138151,
        "outputs.operating_income": 56519.8,
        "outputs.operating_margin": 0.652661869838993
      }
    },
    {
      "name": "bull",
      "probability": 0.25,
      "revenue": 105843.1,
      "operating_income": 70948.2,
      "scalars": {
        "inputs.cost_of_revenue": 26486.9,
        "inputs.net_income": 65656.8,
        "inputs.operating_expenses": 8408.0,
        "inputs.revenue": 105843.1,
        "outputs.gross_margin": 0.749753172384407,
        "outputs.gross_profit": 79356.2,
        "outputs.net_margin": 0.620321967138151,
        "outputs.operating_income": 70948.2,
        "outputs.operating_margin": 0.670314833938159
      }
    }
  ],
  "expected_values": {
    "outputs.operating_income": 63734.0
  },
  "comparison": {
    "descriptions": {
      "base": "Base",
      "bear": "Bear",
      "bull": "Bull"
    },
    "scenarios": [
      "bull",
      "base",
      "bear"
    ],
    "values": {
      "inputs.cost_of_revenue": {
        "base": 24079.0,
        "bear": 21671.1,
        "bull": 26486.9
      },
      "inputs.net_income": {
        "base": 59688.0,
        "bear": 53719.2,
        "bull": 65656.8
      },
      "inputs.operating_expenses": {
        "base": 8408.0,
        "bear": 8408.0,
        "bull": 8408.0
      },
      "inputs.revenue": {
        "base": 96221.0,
        "bear": 86598.9,
        "bull": 105843.1
      },
      "outputs.gross_margin": {
        "base": 0.749753172384407,
        "bear": 0.749753172384407,
        "bull": 0.749753172384407
      },
      "outputs.gross_profit": {
        "base": 72142.0,
        "bear": 64927.8,
        "bull": 79356.2
      },
      "outputs.net_margin": {
        "base": 0.620321967138151,
        "bear": 0.620321967138151,
        "bull": 0.620321967138151
      },
      "outputs.operating_income": {
        "base": 63734.0,
        "bear": 56519.8,
        "bull": 70948.2
      },
      "outputs.operating_margin": {
        "base": 0.662371000093535,
        "bear": 0.652661869838993,
        "bull": 0.670314833938159
      }
    },
    "variables": [
      "inputs.revenue",
      "inputs.cost_of_revenue",
      "inputs.operating_expenses",
      "inputs.net_income",
      "outputs.gross_profit",
      "outputs.operating_income",
      "outputs.gross_margin",
      "outputs.operating_margin",
      "outputs.net_margin"
    ]
  },
  "break_even_thresholds": {
    "vary": "inputs.revenue",
    "target": "outputs.operating_income",
    "target_value": 0.0,
    "solution": 32486.9999837279,
    "achieved": -1.62721225933637e-05,
    "error": 1.62721225933637e-05,
    "iterations": 36,
    "converged": true
  },
  "assumptions": "Revenue +10% (bull) / -10% (bear); cost of revenue and net income move with revenue; operating expenses fixed. Probabilities 25/50/25 are illustrative."
}

Write a concise brief (400-700 words) with these sections, in this order:

- **Overview** -- One sentence on the company and reporting period.
- **Key Financials** -- Revenue, gross profit, operating income, margins.
  CRITICAL: Use ONLY numbers from the Forge calculation results above.
  Every number must trace back to a specific Forge output field.
- **Margin Analysis** -- Gross margin, operating margin, trends if data allows.
- **Risk Profile** -- P10/P50/P90 ranges for key metrics from Monte Carlo. Top risk drivers from sensitivity (tornado) analysis. Break-even revenue.
- **Scenario Comparison** -- Bull/base/bear outcomes with probabilities. Expected value across scenarios. Key break-even thresholds.
- **Assessment** -- Strengths and concerns these numbers show. No outlook or forecast.

Rules:
- Do NOT invent, estimate, or hallucinate any numbers.
- If a metric is unavailable, say so -- do not fill in approximate figures.
- Format monetary values with $ and appropriate units (e.g. $94.8B, $1.2M).
- Format percentages with a % sign (e.g. 45.2%).
- Be direct and factual.  Say that risk ranges and scenarios describe the stated
  assumptions, not the company's real uncertainty.
