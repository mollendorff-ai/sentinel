_forge_version: "5.1.0"

inputs:
  revenue: 96221
  cost_of_revenue: 24079
  operating_expenses: 8408
  net_income: 59688

outputs:
  gross_profit: {formula: "=inputs.revenue - inputs.cost_of_revenue"}
  operating_income: {formula: "=outputs.gross_profit - inputs.operating_expenses"}
  gross_margin: {formula: "=outputs.gross_profit / inputs.revenue"}
  operating_margin: {formula: "=outputs.operating_income / inputs.revenue"}
  net_margin: {formula: "=inputs.net_income / inputs.revenue"}
