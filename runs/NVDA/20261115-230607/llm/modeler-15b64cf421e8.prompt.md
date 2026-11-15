You are a financial modeler.  Given the earnings data below, write a Forge model
(model format 5.1.0) that calculates the quarter's key metrics.  Forge does the
arithmetic: you write the formulas, never their results.

EARNINGS DATA:
{
  "company": "NVIDIA Corporation",
  "ticker": "NVDA",
  "period": "Q2 FY2027",
  "currency": "USD",
  "revenue": 96221,
  "cost_of_revenue": 24079,
  "operating_expenses": 8408,
  "net_income": 59688
}

The model has two groups.

`inputs` holds four figures, each a plain number copied from the data:
revenue, cost_of_revenue, operating_expenses, net_income.

`outputs` holds five results, each a formula over the inputs and other outputs:
- gross_profit: what the statements of operations call gross margin, in dollars
- operating_income: as the statements of operations define it
- gross_margin: gross profit as a share of revenue (0.25 means 25%)
- operating_margin: operating income as a share of revenue
- net_margin: net income as a share of revenue

Forge's format:
- The first line is `_forge_version: "5.1.0"`.
- An input is a plain number: `revenue: 94800`.  Use raw numbers, not "$94.8B".
- An output is `{formula: "=<expression>"}`, written like an Excel formula; never
  write its value.
- A formula names a field as `group.field`, for example `inputs.revenue`.
- Use only the four figures in the data; do NOT invent numbers.  If one is null or
  missing, leave it out, and leave out every output that needs it.
- Return ONLY the YAML content, no markdown fences, no commentary.

Sentinel compares two of Forge's results with the subtotals the filing prints, so
a wrong formula stops the run.
