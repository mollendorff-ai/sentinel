You are a financial analyst writing a short, factual brief for a demonstration
of Forge in an AI pipeline.  It is not investment advice: give no recommendation,
price target or forecast.

COMPANY: AAPL
PERIOD: Q4 FY2026

EXTRACTED DATA (from public filings):
{
  "company": "Apple Inc.",
  "ticker": "AAPL",
  "period": "Q4 FY2026",
  "currency": "USD",
  "revenue": 114477,
  "cost_of_revenue": 59657,
  "gross_profit": 54820,
  "operating_expenses": 19189,
  "operating_income": 35631,
  "net_income": 30711,
  "eps": 2.1,
  "shares_outstanding": 14630318,
  "input": {
    "path": "inputs/AAPL/FY2026-Q4",
    "period": "FY2026-Q4",
    "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000024/a8-kex991q4202609262026.htm",
    "expected_checked_by_person": true,
    "expected_mismatches": []
  }
}

FORGE CALCULATION RESULTS (deterministic -- these are the authoritative numbers):
{
  "inputs.cost_of_revenue": 59657.0,
  "inputs.net_income": 30711.0,
  "inputs.operating_expenses": 19189.0,
  "inputs.revenue": 114477.0,
  "outputs.gross_margin": 0.478873485503638,
  "outputs.gross_profit": 54820.0,
  "outputs.net_margin": 0.268272229356115,
  "outputs.operating_income": 35631.0,
  "outputs.operating_margin": 0.311250294819047
}

RISK ANALYSIS (Monte Carlo + Sensitivity):
{
  "monte_carlo": {
    "output": "outputs.operating_income",
    "iterations": 10000,
    "mean": 35631.0695495508,
    "std_dev": 13049.7967591814,
    "p10": 18642.1101981257,
    "p50": 35701.7822489257,
    "p90": 52334.2199832037
  },
  "tornado": {
    "output": "outputs.operating_income",
    "base_value": 35631.0,
    "bars": [
      {
        "input_name": "inputs.revenue",
        "output_at_low": 24183.3,
        "output_at_high": 47078.7,
        "swing": 22895.4,
        "abs_swing": 22895.4,
        "input_low": 103029.3,
        "input_high": 125924.7
      },
      {
        "input_name": "inputs.cost_of_revenue",
        "output_at_low": 41596.7,
        "output_at_high": 29665.3,
        "swing": -11931.4,
        "abs_swing": 11931.4,
        "input_low": 53691.3,
        "input_high": 65622.7
      },
      {
        "input_name": "inputs.operating_expenses",
        "output_at_low": 37549.9,
        "output_at_high": 33712.1,
        "swing": -3837.8,
        "abs_swing": 3837.8,
        "input_low": 17270.1,
        "input_high": 21107.9
      },
      {
        "input_name": "inputs.net_income",
        "output_at_low": 35631.0,
        "output_at_high": 35631.0,
        "swing": 0.0,
        "abs_swing": 0.0,
        "input_low": 27639.9,
        "input_high": 33782.1
      }
    ],
    "total_variance": 38664.6
  },
  "break_even": {
    "vary": "inputs.revenue",
    "target": "outputs.operating_income",
    "target_value": 0.0,
    "solution": 78846.0000438298,
    "achieved": 4.38297865912318e-05,
    "error": 4.38297865912318e-05,
    "iterations": 35,
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
      "revenue": 114477.0,
      "operating_income": 35631.0,
      "scalars": {
        "inputs.cost_of_revenue": 59657.0,
        "inputs.net_income": 30711.0,
        "inputs.operating_expenses": 19189.0,
        "inputs.revenue": 114477.0,
        "outputs.gross_margin": 0.478873485503638,
        "outputs.gross_profit": 54820.0,
        "outputs.net_margin": 0.268272229356115,
        "outputs.operating_income": 35631.0,
        "outputs.operating_margin": 0.311250294819047
      }
    },
    {
      "name": "bear",
      "probability": 0.25,
      "revenue": 103029.3,
      "operating_income": 30149.0,
      "scalars": {
        "inputs.cost_of_revenue": 53691.3,
        "inputs.net_income": 27639.9,
        "inputs.operating_expenses": 19189.0,
        "inputs.revenue": 103029.3,
        "outputs.gross_margin": 0.478873485503638,
        "outputs.gross_profit": 49338.0,
        "outputs.net_margin": 0.268272229356115,
        "outputs.operating_income": 30149.0,
        "outputs.operating_margin": 0.292625495854092
      }
    },
    {
      "name": "bull",
      "probability": 0.25,
      "revenue": 125924.7,
      "operating_income": 41113.0,
      "scalars": {
        "inputs.cost_of_revenue": 65622.7,
        "inputs.net_income": 33782.1,
        "inputs.operating_expenses": 19189.0,
        "inputs.revenue": 125924.7,
        "outputs.gross_margin": 0.478873485503638,
        "outputs.gross_profit": 60302.0,
        "outputs.net_margin": 0.268272229356115,
        "outputs.operating_income": 41113.0,
        "outputs.operating_margin": 0.326488766699464
      }
    }
  ],
  "expected_values": {
    "outputs.operating_income": 35631.0
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
        "base": 59657.0,
        "bear": 53691.3,
        "bull": 65622.7
      },
      "inputs.net_income": {
        "base": 30711.0,
        "bear": 27639.9,
        "bull": 33782.1
      },
      "inputs.operating_expenses": {
        "base": 19189.0,
        "bear": 19189.0,
        "bull": 19189.0
      },
      "inputs.revenue": {
        "base": 114477.0,
        "bear": 103029.3,
        "bull": 125924.7
      },
      "outputs.gross_margin": {
        "base": 0.478873485503638,
        "bear": 0.478873485503638,
        "bull": 0.478873485503638
      },
      "outputs.gross_profit": {
        "base": 54820.0,
        "bear": 49338.0,
        "bull": 60302.0
      },
      "outputs.net_margin": {
        "base": 0.268272229356115,
        "bear": 0.268272229356115,
        "bull": 0.268272229356115
      },
      "outputs.operating_income": {
        "base": 35631.0,
        "bear": 30149.0,
        "bull": 41113.0
      },
      "outputs.operating_margin": {
        "base": 0.311250294819047,
        "bear": 0.292625495854092,
        "bull": 0.326488766699464
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
    "solution": 78846.0000438298,
    "achieved": 4.38297865912318e-05,
    "error": 4.38297865912318e-05,
    "iterations": 35,
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
