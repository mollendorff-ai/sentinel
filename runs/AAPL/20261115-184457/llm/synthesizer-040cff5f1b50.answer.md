# Apple Inc. (AAPL): Q4 FY2026 brief

## Overview

Apple Inc. reported its fourth quarter of fiscal 2026, the three months ended September 26, 2026, in a press release filed with the SEC on November 2, 2026.

## Key Financials

All figures in USD, from Forge's calculation results.

- Revenue: $114,477M (`inputs.revenue`)
- Cost of revenue: $59,657M (`inputs.cost_of_revenue`)
- Gross profit: $54,820M (`outputs.gross_profit`)
- Operating expenses: $19,189M (`inputs.operating_expenses`)
- Operating income: $35,631M (`outputs.operating_income`)
- Net income: $30,711M (`inputs.net_income`)

Forge's gross profit and operating income equal the figures printed in the filing's statement of operations, and the four inputs match the figures checked by a person in `expected.yaml`.

## Margin Analysis

- Gross margin: 47.9% (`outputs.gross_margin`, 0.4789)
- Operating margin: 31.1% (`outputs.operating_margin`, 0.3113)
- Net margin: 26.8% (`outputs.net_margin`, 0.2683)

This is the first run for this ticker, so there is no earlier period to show a trend.

## Risk Profile

These ranges describe Sentinel's stated assumptions (each input varied by 10%, drawn independently), not Apple's real uncertainty.

- Operating income over 10,000 Monte Carlo iterations: P10 $18,642M, P50 $35,702M, P90 $52,334M (mean $35,631M, standard deviation $13,050M).
- Tornado, largest swing first: revenue ($22,895M swing in operating income), cost of revenue ($11,931M), operating expenses ($3,838M). Net income has no effect on operating income (swing $0M).
- Break-even revenue: $78,846M (`break_even.solution`), the revenue at which operating income reaches zero with the other inputs held.

## Scenario Comparison

Also assumptions, not forecasts: revenue moves ±10%, cost of revenue and net income move with it, operating expenses stay fixed, and the 25/50/25 probabilities are illustrative.

| Scenario | Probability | Revenue | Operating income | Operating margin |
| --- | ---: | ---: | ---: | ---: |
| Bull | 25% | $125,924.7M | $41,113M | 32.6% |
| Base | 50% | $114,477M | $35,631M | 31.1% |
| Bear | 25% | $103,029.3M | $30,149M | 29.3% |

Forge's probability-weighted operating income is $35,631M (`expected_values`). The break-even revenue threshold is $78,846M, as above.

## Assessment

- **Strengths these numbers show:** a gross margin of 47.9% and an operating margin of 31.1% in the quarter; operating income stays positive in all three scenarios, and the break-even revenue of $78,846M is well below the quarter's $114,477M.
- **Concerns these numbers show:** operating income is most sensitive to revenue, then to cost of revenue; with operating expenses fixed, operating margin moves from 29.3% to 32.6% across the scenarios. The ranges rest on one quarter and fixed ±10% assumptions, so they show how the model responds, not what will happen.
