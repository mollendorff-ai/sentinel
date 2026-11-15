# Findings for Forge and Ref

What Sentinel, as a program, found hard about Forge and Ref while it was rebuilt as Forge's demo (ADR-012). Each is to be reported to that project as a roadmap item; this file keeps only those not yet reported.

## Forge (v10.0.0-rc.26)

- **docs/MCP.md says a Monte Carlo section needs `enabled: true`.** `forge simulate` never reads the flag (`MonteCarloConfig::enabled` is set only by the CLI itself), and Sentinel's models run without it.
- **docs/MCP.md says `forge_functions` lists 173 functions.** The project description and README count 203.
- **`forge validate` on a model never calculated says "All scalar values match their formulas!"** with nothing stored to compare (already Forge's T1-AGENT-FRICTION). Sentinel relies on validate failing on a broken formula, which it does, because it calculates the model.
- **A tornado input that cannot move the output is listed with a swing of 0** (`inputs.net_income` against `outputs.operating_income`) and no note that it is not upstream of the output. A program has to work out the dependency itself to leave it out.

## Ref (1.8.4)

- **No way to set the user agent.** SEC EDGAR refuses requests that do not declare a name and a contact email ("Your Request Originates from an Undeclared Automated Tool", HTTP 403), so Ref cannot fetch any SEC filing. The first input was downloaded with `curl` instead (ADR-012, addendum).
