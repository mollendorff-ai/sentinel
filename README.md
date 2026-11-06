[![CI](https://github.com/mollendorff-ai/sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/mollendorff-ai/sentinel/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/lctavares/fdd0cc841540cef69f14f92594512e4f/raw/sentinel-coverage.json)](https://github.com/mollendorff-ai/sentinel/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/lctavares/fdd0cc841540cef69f14f92594512e4f/raw/sentinel-tests.json)](https://github.com/mollendorff-ai/sentinel/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

# Sentinel

**Earnings analysis with multi-agent AI. Prototype, built with AI assistance. Not financial advice.**

LangGraph agents fetch earnings pages, extract the figures with an LLM, calculate metrics, risk ranges and scenarios in Forge, and write a short analysis brief. The arithmetic is done by Forge, not by the LLM. The inputs are still read by the LLM from web pages, so check the extracted figures (saved in `raw_data.json`) before relying on a brief.

```mermaid
C4Container
    title Sentinel — C4 Container Diagram

    Person(analyst, "Analyst", "Requests earnings analysis via CLI")
    System_Ext(mcp_client, "MCP Clients", "Claude Code, Claude Desktop, other LLM agents")

    Container_Boundary(sentinel, "Sentinel") {
        Container(mcp_server, "MCP Server", "FastMCP / stdio", "sentinel_analyze + sentinel_resume — two-tool HITL flow")
        Container(pipeline, "LangGraph Pipeline", "StateGraph", "Conditional routing, self-correction loops, HITL approval gate, streaming, checkpointing")
        Container(research, "Research Agent", "LangChain", "Fetches earnings data, extracts financials")
        Container(retriever, "Retriever Agent", "Python", "Looks up past quarters for the ticker, populates trend context")
        Container(modeler, "Modeler Agent", "LangChain", "Generates Forge YAML, validates, calculates margins")
        Container(risk, "Risk Analyst", "LangChain", "Monte Carlo simulation, tornado sensitivity")
        Container(scenario, "Scenario Planner", "LangChain", "Bull / base / bear scenario analysis")
        Container(synth, "Synthesizer", "LangChain", "Executive brief with traceable numbers and trend analysis")
        ContainerDb(db, "SQLite", "Checkpointer", "Persists state for resumable runs")
        ContainerDb(qdrant, "Qdrant", "Vector Store", "Historical earnings embeddings for trend retrieval")
    }

    System(forge, "Forge", "Our MCP server: formula engine with Monte Carlo, scenarios and sensitivity")
    System(ref, "Ref", "Our MCP server: headless Chrome, renders JavaScript-heavy pages, structured JSON")
    System_Ext(llm, "LLM Provider", "Claude / GPT / Gemini — swappable via env var")
    System_Ext(langsmith, "LangSmith", "Observability: traces, run names, tags, metadata")

    Rel(analyst, pipeline, "Runs", "CLI / Makefile")
    Rel(mcp_client, mcp_server, "Calls tools", "MCP / stdio")
    Rel(mcp_server, pipeline, "Drives")
    Rel(pipeline, research, "Dispatches")
    Rel(pipeline, retriever, "Dispatches")
    Rel(pipeline, modeler, "Dispatches")
    Rel(pipeline, risk, "Full mode only")
    Rel(pipeline, scenario, "Full mode only")
    Rel(pipeline, synth, "Dispatches")
    Rel(research, ref, "Fetches earnings", "MCP / stdio")
    Rel(retriever, qdrant, "Queries history", "local")
    Rel(modeler, forge, "Validate + calculate", "MCP / stdio")
    Rel(risk, forge, "Simulate + tornado", "MCP / stdio")
    Rel(scenario, forge, "Scenarios + compare", "MCP / stdio")
    Rel(research, llm, "Extracts financials", "API")
    Rel(modeler, llm, "Generates YAML", "API")
    Rel(risk, llm, "Augments model", "API")
    Rel(scenario, llm, "Generates scenarios", "API")
    Rel(synth, llm, "Produces brief", "API")
    Rel(pipeline, db, "Checkpoints state")
    Rel(pipeline, qdrant, "Ingests after run", "local")
    Rel(pipeline, langsmith, "Traces runs", "HTTPS")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

**The LLM reads and writes. Forge calculates. Code builds the risk and scenario ranges.** Forge's results are deterministic; the figures fed into it come from an LLM reading web pages.

## Ecosystem

Sentinel is part of the [mollendorff-ai](https://github.com/mollendorff-ai) platform. All three projects are designed to work together via [MCP](https://modelcontextprotocol.io/) (Model Context Protocol):

| Project | Role | Details |
| ------- | ---- | ------- |
| **[Sentinel](https://github.com/mollendorff-ai/sentinel)** | Multi-agent orchestrator | LangGraph pipeline: 6 agents, Qdrant history, HITL approval gate, streaming, conditional routing, self-correction, checkpointing. Also an MCP server (2 tools) |
| **[Forge](https://github.com/mollendorff-ai/forge)** | Financial modeling engine | MCP server: 20 tools, Excel-style formulas, Monte Carlo, scenarios, sensitivity |
| **[Ref](https://github.com/mollendorff-ai/ref)** | Web data ingestion | MCP server: 6 tools, headless Chrome, renders JavaScript-heavy pages, structured JSON |

Sentinel orchestrates. Forge calculates. Ref fetches. The LLM reasons -- and is swappable with one env var.

## Architecture

| Agent | Role | Tools |
| ----- | ---- | ----- |
| **Research** | Fetches earnings pages (currently two Macrotrends pages), extracts revenue, margins, guidance | Ref (MCP) |
| **Retriever** | Looks up the ticker's past quarters in a local Qdrant store; populates historical context for trend analysis | Qdrant |
| **Modeler** | Writes a Forge YAML model of gross, operating and net margins from the extracted data | Forge validate + calculate (MCP) |
| **Risk Analyst** | Adds Monte Carlo distributions to uncertain inputs, identifies top risk drivers | Forge simulate + tornado (MCP) |
| **Scenario Planner** | Generates bull/base/bear scenarios from guidance language, probability-weighted | Forge scenarios + compare (MCP) |
| **Synthesizer** | Produces an executive brief: key financials, margins, risk ranges, scenarios, trend, assessment | Reads all Forge outputs + historical context |

The LangGraph pipeline handles routing, error recovery, and agent self-correction. In `--quick` mode, Risk Analyst and Scenario Planner are skipped via conditional edges. In `--hitl` mode, the pipeline pauses before the Synthesizer for analyst review — approve to generate the brief, or reject with feedback to rerun with context.

## Why This Design

LLMs are unreliable at arithmetic. Sentinel keeps a clear boundary:

- **Any LLM does:** extraction from web pages, the model YAML, and the written brief
- **Forge does:** the calculations: margins, Monte Carlo, tornado sensitivity, break-even, scenario math
- **Ref does:** web page fetching (headless Chrome, JavaScript-heavy pages)

Swap the LLM provider with one env var (`SENTINEL_LLM_PROVIDER`). The orchestration layer doesn't care which model reasons -- only that Forge calculates.

The agent writes YAML. Forge validates the formulas. If the model is wrong, Forge returns errors and the agent retries (up to 3 times). Forge fixes the arithmetic; it cannot tell whether the LLM read the right number from the page.

## Stack

| Layer | Technology |
| ----- | ---------- |
| Orchestration | LangGraph (Python) -- [why Python?](docs/adr/001-python-over-typescript.md) |
| Persistence | SQLite checkpointer ([why?](docs/adr/007-sqlite-checkpointer.md)) |
| HITL | `interrupt_before` + checkpointer -- opt-in via `--hitl`; same mechanism drives the MCP server ([ADR-010](docs/adr/010-hitl-interrupt-before-synthesizer.md)) |
| MCP Server | FastMCP over stdio -- `sentinel_analyze` + `sentinel_resume` ([ADR-011](docs/adr/011-sentinel-as-mcp-server.md)) |
| History | Local Qdrant, looked up by ticker ([why?](docs/adr/009-qdrant-rag-historical-earnings.md)) -- no embedding model, no API key |
| Observability | LangSmith (per-ticker run names, tags, metadata) |
| Financial modeling | [Forge](https://github.com/mollendorff-ai/forge) via MCP (20 tools: formulas, Monte Carlo, scenarios, sensitivity) |
| Data ingestion | [Ref](https://github.com/mollendorff-ai/ref) via MCP (6 tools, headless Chrome, structured JSON) |
| LLM | Any LangChain-compatible model -- [swap with one env var](docs/adr/004-multi-provider-llm-support.md) |

## Roadmap

| Version | Summary | Status |
| ------- | ------- | ------ |
| v0.1.0 | Project scaffold, Forge MCP, Ref MCP | Shipped |
| v0.2.0 | 3-agent pipeline (Research, Modeler, Synthesizer) | Shipped |
| v0.3.0 | 5-agent pipeline, conditional routing, Monte Carlo | Shipped |
| v0.4.0 | Persistence, observability, multi-ticker batch, error handling | Shipped |
| v0.5.0 | C4 architecture diagram, dynamic badges, README showcase | Shipped |
| v0.6.0 | RAG with Qdrant -- historical earnings for trend analysis | Shipped |
| v0.7.0 | Human-in-the-loop approval gate, real-time streaming | Shipped |
| v0.8.0 | Sentinel as MCP server -- two-tool HITL flow for Claude Code / Desktop | Shipped |
| v0.8.1 | Runs end to end: async checkpointer, Forge failure handling, Qdrant history, ticker validation, prompts for current Forge | Current |

See [CHANGELOG](CHANGELOG.md) for details.

## Getting Started

### Prerequisites

- Python 3.11+
- [Forge](https://github.com/mollendorff-ai/forge) 10.0.0-beta.11 or newer, with `forge` on your PATH (build with `cargo build --release`; the first build takes several minutes)
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
make demo                        # Full 6-agent analysis for AAPL
make demo TICKER="AAPL MSFT"     # Multi-ticker batch mode
make demo-quick                  # Quick 3-agent mode (skip risk + scenarios)
python -m sentinel --hitl AAPL   # Full analysis with analyst approval gate
make check                       # Lint + unit tests (100% coverage required)
make test-integration            # Needs forge and ref on PATH
```

Results are saved to `output/{TICKER}/{timestamp}/` with JSON, markdown, and YAML artifacts.

## Status and limits

- Prototype, built with AI assistance (see the commit history). Not financial advice; do not use it to make investment decisions.
- The figures come from an LLM reading two Macrotrends pages per ticker. The LLM can misread a page, and Macrotrends' terms of service restrict automated access, so check their terms before running it. Replacing this source (for example with SEC filings) is on the roadmap.
- Risk ranges and scenarios are built in code with fixed assumptions (inputs ±10%; scenarios move revenue ±10% with cost of revenue and net income, operating expenses fixed) and applied to the latest quarter. They describe those assumptions, not the company's real uncertainty.
- The brief is written by an LLM from Forge's results. Nothing checks the text against the numbers automatically.
- Not yet run against live data by the maintainer after the 0.8.1 fixes; see the CHANGELOG.

## MCP Server

Sentinel exposes itself as an MCP server over stdio, consistent with Forge and Ref.
Two tools implement the HITL flow from v0.7.0 ([ADR-011](docs/adr/011-sentinel-as-mcp-server.md)):

| Tool | Description |
| ---- | ----------- |
| `sentinel_analyze` | Run the full pipeline to the analyst approval gate. Returns `thread_id` + draft snapshot. |
| `sentinel_resume` | Resume from checkpoint. Pass `decision="approve"` or `"reject"` with optional `feedback`. Returns final brief. |

### Quick start

Add to your MCP client configuration (e.g. `~/.claude/mcp.json`):

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

Then in Claude Code or Claude Desktop:

1. Call `sentinel_analyze` with a ticker to get back `thread_id` and draft financials
2. Review the draft (risk ranges, scenario projections, historical trend)
3. Call `sentinel_resume` with `thread_id` + `decision="approve"` to get the final brief

## License

[MIT](LICENSE)
