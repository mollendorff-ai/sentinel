# NVIDIA Corporation (NVDA): Q2 FY2027 brief

## Overview

NVIDIA Corporation reported its second quarter of fiscal 2027, the three months ended July 26, 2026, in a press release filed with the SEC on August 26, 2026.

## Key Financials

All figures in USD, from Forge's calculation results.

- Revenue: $96,221M (`inputs.revenue`)
- Cost of revenue: $24,079M (`inputs.cost_of_revenue`)
- Gross profit: $72,142M (`outputs.gross_profit`)
- Operating expenses: $8,408M (`inputs.operating_expenses`)
- Operating income: $63,734M (`outputs.operating_income`)
- Net income: $59,688M (`inputs.net_income`)

Forge's gross profit and operating income equal the subtotals printed in the filing's statement of income, and the four inputs match the figures checked by a person in `expected.yaml`. All are GAAP figures; the release's non-GAAP figures are not used.

## Margin Analysis

- Gross margin: 75.0% (`outputs.gross_margin`, 0.7498)
- Operating margin: 66.2% (`outputs.operating_margin`, 0.6624)
- Net margin: 62.0% (`outputs.net_margin`, 0.6203)

This is the first run for this ticker, so there is no earlier period to show a trend.

## Risk Profile

These ranges describe Sentinel's stated assumptions (each input varied by 10%, drawn independently), not NVIDIA's real uncertainty.

- Operating income over 10,000 Monte Carlo iterations: P10 $50,782M, P50 $63,724M, P90 $76,416M (mean $63,734M, standard deviation $9,952M).
- Tornado, largest swing first: revenue ($19,244M swing in operating income), cost of revenue ($4,816M), operating expenses ($1,682M). Net income has no effect on operating income (swing $0M).
- Break-even revenue: $32,487M (`break_even.solution`), the revenue at which operating income reaches zero with the other inputs held.

## Scenario Comparison

Also assumptions, not forecasts: revenue moves ±10%, cost of revenue and net income move with it, operating expenses stay fixed, and the 25/50/25 probabilities are illustrative.

| Scenario | Probability | Revenue | Operating income | Operating margin |
| --- | ---: | ---: | ---: | ---: |
| Bull | 25% | $105,843.1M | $70,948.2M | 67.0% |
| Base | 50% | $96,221M | $63,734M | 66.2% |
| Bear | 25% | $86,598.9M | $56,519.8M | 65.3% |

Forge's probability-weighted operating income is $63,734M (`expected_values`). The break-even revenue threshold is $32,487M, as above.

## Assessment

- **Strengths these numbers show:** a gross margin of 75.0% and an operating margin of 66.2% in the quarter; operating expenses are $8,408M against gross profit of $72,142M, so operating income stays positive in all three scenarios, and the break-even revenue of $32,487M is about a third of the quarter's $96,221M.
- **Concerns these numbers show:** operating income depends mostly on revenue, whose swing is about four times that of cost of revenue. Net income ($59,688M) is close to operating income ($63,734M); the items between them are not in this model, so the net margin is a ratio of checked figures, not something Forge explains. The ranges rest on one quarter and fixed ±10% assumptions, so they show how the model responds, not what will happen.
