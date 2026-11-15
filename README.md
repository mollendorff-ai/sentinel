[![CI](https://github.com/mollendorff-ai/sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/mollendorff-ai/sentinel/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/lctavares/fdd0cc841540cef69f14f92594512e4f/raw/sentinel-coverage.json)](https://github.com/mollendorff-ai/sentinel/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/lctavares/fdd0cc841540cef69f14f92594512e4f/raw/sentinel-tests.json)](https://github.com/mollendorff-ai/sentinel/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

# Sentinel

**A demonstration of [Forge](https://github.com/mollendorff-ai/forge) in an AI pipeline. Prototype, built with AI assistance. Not financial advice.**

An AI agent reads a company's quarterly results, writes a Forge model, and Forge validates and calculates it. The agent reads Forge's numbers, never its own arithmetic, and the run's model and results go into git as a pull request for a person to review. It is the fourth workflow of Forge's [docs/WORKFLOWS.md](https://github.com/mollendorff-ai/forge/blob/main/docs/WORKFLOWS.md), the AI pipeline, running for real.

> **Status (2026-11-15): being rebuilt as Forge's demo ([ADR-012](docs/adr/012-sentinel-as-forge-demo.md)).** The code today is 0.8.1: it still reads two live Macrotrends pages and keeps history in Qdrant, and it has not yet been run end to end with a real LLM. Version 0.9.0 replaces both with a saved input and files in git, and runs unattended in GitHub Actions. See [Roadmap](#roadmap).

## How a demo run works (0.9.0, being built)

```mermaid
sequenceDiagram
    participant W as GitHub Actions<br/>(started by hand)
    participant S as Sentinel agents
    participant F as Forge
    participant G as git
    actor R as Reviewer
    W->>S: inputs/TICKER/period: a saved SEC earnings release
    S->>S: LLM extracts the figures
    S->>S: compare with expected.yaml, typed by a person
    S->>S: LLM writes model.yaml
    loop until Forge accepts it
        S->>F: forge validate, forge calculate
        F-->>S: the reason it failed, or the results
    end
    S->>F: simulate, tornado, scenarios
    F-->>S: risk ranges and scenarios
    S->>S: LLM writes the brief from Forge's numbers
    S->>G: branch, commit input, model, results, brief; open a pull request
    R->>G: review the diff of figures, formulas and results; merge
```

**Two checks, two different questions.** Forge checks the arithmetic: every number in the results comes from a formula it calculated. It cannot tell whether the LLM read the right figure from the filing, so each saved input comes with an `expected.yaml` of its headline figures, typed by a person, and a run whose extraction differs fails.

## What runs today (0.8.1)

| Agent | Role | Tools |
| ----- | ---- | ----- |
| **Research** | Fetches two Macrotrends pages for the ticker, extracts revenue, margins, guidance (to be replaced by a saved input) | Ref (MCP) |
| **Retriever** | Looks up the ticker's past quarters in a local Qdrant store (to be replaced by earlier runs' files in git) | Qdrant |
| **Modeler** | Writes a Forge YAML model of gross, operating and net margins from the extracted data, retrying up to 3 times when Forge refuses it | Forge validate + calculate (MCP) |
| **Risk Analyst** | Adds Monte Carlo distributions and tornado ranges to the inputs, built in code (inputs ±10%) | Forge simulate + tornado (MCP) |
| **Scenario Planner** | Bull / base / bear scenarios, built in code (revenue ±10%, probability-weighted) | Forge scenarios + compare (MCP) |
| **Synthesizer** | Writes the brief from Forge's results | Reads all Forge outputs |

In `--quick` mode the Risk Analyst and Scenario Planner are skipped. In `--hitl` mode the pipeline pauses before the Synthesizer for approval. Both stay, but the demo's human review is the pull request.

**Limits today:**

- The figures come from an LLM reading live web pages, and Macrotrends' terms restrict automated access. 0.9.0 removes this.
- Risk ranges and scenarios use fixed assumptions (±10%) applied to the latest quarter. They describe those assumptions, not the company's real uncertainty.
- The brief is written by an LLM from Forge's results. Nothing yet checks the text against the numbers.

## Stack

| Layer | Technology |
| ----- | ---------- |
| Orchestration | LangGraph (Python) -- [why Python?](docs/adr/001-python-over-typescript.md) |
| Calculation | [Forge](https://github.com/mollendorff-ai/forge) via MCP, the only calculator |
| Persistence | SQLite checkpointer ([why?](docs/adr/007-sqlite-checkpointer.md)) |
| Record and review | git and a pull request ([ADR-012](docs/adr/012-sentinel-as-forge-demo.md), 0.9.0) |
| HITL | `interrupt_before` + checkpointer, opt-in via `--hitl` ([ADR-010](docs/adr/010-hitl-interrupt-before-synthesizer.md)) |
| MCP server | FastMCP over stdio: `sentinel_analyze` + `sentinel_resume` ([ADR-011](docs/adr/011-sentinel-as-mcp-server.md)) |
| History | Local Qdrant today; earlier runs' files in git in 0.9.0 ([ADR-012](docs/adr/012-sentinel-as-forge-demo.md)) |
| LLM | Any LangChain-compatible model -- [swap with one env var](docs/adr/004-multi-provider-llm-support.md) |
| Observability | LangSmith, optional and off by default |

## Roadmap

| Version | Summary | Status |
| ------- | ------- | ------ |
| v0.1.0 to v0.8.0 | Agents, Forge and Ref over MCP, risk and scenarios, checkpoints, Qdrant history, HITL, MCP server | Shipped |
| v0.8.1 | Runs end to end on Forge beta.11 in tests: async checkpointer, Forge failure handling, ticker validation | Current |
| v0.9.0 | Forge demo: a saved SEC input checked against `expected.yaml`, no Qdrant, Forge pinned and verified, an unattended run in GitHub Actions that opens a pull request | Next |

The full list, with each item's acceptance, is in [.asimov/roadmap.yaml](.asimov/roadmap.yaml). History is in the [CHANGELOG](CHANGELOG.md).

## Getting Started (0.8.1)

### Prerequisites

- Python 3.11+
- [Forge](https://github.com/mollendorff-ai/forge) 10.0.0-beta.11 or newer, with `forge` on your PATH
- [Ref](https://github.com/mollendorff-ai/ref) 1.6.0 or newer, with `ref` on your PATH, and Chrome or Chromium installed
- An API key for your LLM provider (default: Anthropic)

### Install

```bash
git clone https://github.com/mollendorff-ai/sentinel.git
cd sentinel
make setup    # creates venv, installs deps, copies .env
# Edit .env with your API keys (Sentinel loads it automatically)
```

### Run

```bash
make demo                        # Full analysis for AAPL
make demo-quick                  # Skip risk + scenarios
python -m sentinel --hitl AAPL   # Full analysis with an approval gate
make check                       # Lint + unit tests (100% coverage required)
make test-integration            # Needs forge and ref on PATH
```

Results are saved to `output/{TICKER}/{timestamp}/` with JSON, markdown, and YAML artifacts.

## MCP Server

Sentinel exposes itself as an MCP server over stdio ([ADR-011](docs/adr/011-sentinel-as-mcp-server.md)). It is not part of the demo.

| Tool | Description |
| ---- | ----------- |
| `sentinel_analyze` | Run the full pipeline to the approval gate. Returns `thread_id` + draft snapshot. |
| `sentinel_resume` | Resume from checkpoint. Pass `decision="approve"` or `"reject"` with optional `feedback`. Returns final brief. |

```json
{
  "mcpServers": {
    "sentinel": {
      "command": "python",
      "args": ["-m", "sentinel", "mcp"],
      "cwd": "/path/to/sentinel"
    }
  }
}
```

## License

[MIT](LICENSE)
