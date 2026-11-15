[![CI](https://github.com/mollendorff-ai/sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/mollendorff-ai/sentinel/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/lctavares/fdd0cc841540cef69f14f92594512e4f/raw/sentinel-coverage.json)](https://github.com/mollendorff-ai/sentinel/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/lctavares/fdd0cc841540cef69f14f92594512e4f/raw/sentinel-tests.json)](https://github.com/mollendorff-ai/sentinel/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

# Sentinel

**A demonstration of [Forge](https://github.com/mollendorff-ai/forge) in an AI pipeline. Prototype, built with AI assistance. Not financial advice.**

An AI agent reads a company's quarterly results, writes a Forge model, and Forge validates and calculates it. The agent reads Forge's numbers, never its own arithmetic, and the run's model and results go into git as a pull request for a person to review. It is the fourth workflow of Forge's [docs/WORKFLOWS.md](https://github.com/mollendorff-ai/forge/blob/main/docs/WORKFLOWS.md), the AI pipeline, running for real ([ADR-012](docs/adr/012-sentinel-as-forge-demo.md)).

> **Status (2026-11-15):** 0.9.0 is built and tested: the saved input, the expected-figure check, Forge pinned, and the demo workflow. In CI the whole pipeline runs against the real Forge on the saved Apple filing, with a scripted LLM, and Forge's operating income equals the filing's (35,631 million). **Not yet done:** a person checking `expected.yaml`, and the first run with a real LLM in GitHub Actions.

## How a demo run works

```mermaid
sequenceDiagram
    participant W as GitHub Actions<br/>(Demo, started by hand)
    participant S as Sentinel agents
    participant F as Forge
    participant G as git
    actor R as Reviewer
    W->>S: inputs/AAPL/FY2026-Q4: Apple's earnings release, as filed with the SEC
    S->>S: LLM extracts the figures
    S->>S: compare with expected.yaml, checked by a person; stop if they differ
    S->>S: LLM writes model.yaml (Forge model format 5.1.0)
    loop until Forge accepts it
        S->>F: forge validate, forge calculate
        F-->>S: the reason it failed, or the results
    end
    S->>F: simulate, tornado, break-even, scenarios
    F-->>S: risk ranges and scenarios
    S->>S: LLM writes the brief from Forge's numbers
    S->>G: branch, commit runs/AAPL/<timestamp>/, open a pull request
    R->>G: review the figures, formulas and results; merge
```

**Two checks, two different questions.** Forge checks the arithmetic: every result comes from a formula it calculated. It cannot tell whether the LLM read the right figure from the filing, so each saved input has an `expected.yaml` of its headline figures, checked by a person, and a run whose extraction differs stops before any model is built.

### A saved input

```text
inputs/AAPL/FY2026-Q4/
  release.htm     the filing as downloaded from SEC EDGAR (checksum in source.yaml)
  release.md      the same document as Markdown (scripts/html_to_markdown.py); what a run reads
  source.yaml     url, filing date, when and how it was saved
  expected.yaml   revenue, cost of revenue, operating expenses, net income; checked: true|false
```

The demo workflow refuses to run on an input whose `expected.yaml` says `checked: false`.

### A run

```text
runs/AAPL/<timestamp>/
  raw_data.json           figures the LLM extracted, and the result of the expected.yaml check
  model.yaml              the Forge model the LLM wrote
  forge_results.json      Forge's results
  risk_analysis.json      Monte Carlo, tornado and break-even (full mode)
  scenario_analysis.json  bull / base / bear (full mode)
  brief.md                the LLM's brief, written from Forge's results
```

Earlier runs are the history: the Retriever reads `raw_data.json` of earlier periods for the ticker from `runs/`.

## Agents

| Agent | Role | Tools |
| ----- | ---- | ----- |
| **Research** | Reads the saved release, extracts the quarter's figures, checks them against `expected.yaml` | LLM |
| **Retriever** | Reads earlier periods for the ticker from `runs/` | Files |
| **Modeler** | Writes a Forge model of gross, operating and net margins, retrying up to 3 times when Forge refuses it | LLM, Forge validate + calculate (MCP) |
| **Risk Analyst** | Monte Carlo, tornado and break-even on the inputs, built in code (inputs ±10%) | Forge simulate + tornado + break-even (MCP) |
| **Scenario Planner** | Bull / base / bear, built in code (revenue ±10%, probability-weighted) | Forge scenarios + compare (MCP) |
| **Synthesizer** | Writes the brief from Forge's results | LLM |

In `--quick` mode the Risk Analyst and Scenario Planner are skipped. `--hitl` and the MCP server stay, but the demo's human review is the pull request.

**Limits:**

- One saved input so far: Apple, fourth quarter of fiscal 2026.
- Risk ranges and scenarios use fixed assumptions (±10%) applied to one quarter. They describe those assumptions, not the company's real uncertainty.
- The brief is written by an LLM from Forge's results. Nothing yet checks the text against the numbers.

## Run the demo (GitHub Actions)

1. A person checks the four figures in `inputs/AAPL/FY2026-Q4/expected.yaml` against the filing at the url in `source.yaml`, and sets `checked: true`.
2. Add the repository secret `ANTHROPIC_API_KEY` (Settings, Secrets and variables, Actions). The model is `claude-sonnet-5-5` unless the variable `SENTINEL_LLM_MODEL` says otherwise.
3. Turn on Settings, Actions, General, "Allow GitHub Actions to create and approve pull requests".
4. Actions, **Demo**, Run workflow. The run opens a pull request with a summary: the figures read, the expected-figure check, Forge's results and the brief.

## Run it locally

```bash
git clone https://github.com/mollendorff-ai/sentinel.git && cd sentinel
make setup                                # venv, dependencies, .env (put your API key in it)
scripts/install-forge.sh                  # the pinned Forge, checksum verified (Linux x86_64)
python -m sentinel AAPL                   # the newest saved input; --period FY2026-Q4 for another
python -m sentinel.summary runs/AAPL/<timestamp>
make check                                # lint + unit tests (100% coverage), no Forge or key needed
make test-integration                     # against the real Forge, no key needed
```

`python -m sentinel` exits with 1 when a run fails (an unreadable input, figures that differ from `expected.yaml`, a model Forge refuses, no brief).

## Stack

| Layer | Technology |
| ----- | ---------- |
| Orchestration | LangGraph (Python) -- [why Python?](docs/adr/001-python-over-typescript.md) |
| Calculation | [Forge](https://github.com/mollendorff-ai/forge) v10.0.0-rc.26 via MCP, the only calculator, pinned in `scripts/install-forge.sh` |
| Record and review | git and a pull request ([ADR-012](docs/adr/012-sentinel-as-forge-demo.md)) |
| Checkpoints | SQLite ([why?](docs/adr/007-sqlite-checkpointer.md)) |
| HITL | `interrupt_before` + checkpointer, opt-in via `--hitl` ([ADR-010](docs/adr/010-hitl-interrupt-before-synthesizer.md)) |
| MCP server | FastMCP over stdio: `sentinel_analyze` + `sentinel_resume` ([ADR-011](docs/adr/011-sentinel-as-mcp-server.md)) |
| LLM | Any LangChain-compatible model -- [swap with one env var](docs/adr/004-multi-provider-llm-support.md) |
| Observability | LangSmith, optional and off by default |

## Roadmap

| Version | Summary | Status |
| ------- | ------- | ------ |
| v0.1.0 to v0.8.1 | Agents, Forge over MCP, risk and scenarios, checkpoints, HITL, MCP server | Shipped |
| v0.9.0 | Forge demo: a saved SEC input checked against `expected.yaml`, no Qdrant, Forge pinned, an unattended run in GitHub Actions that opens a pull request | Built; first real run to come |

Each item, with its acceptance, is in [.asimov/roadmap.yaml](.asimov/roadmap.yaml). History is in the [CHANGELOG](CHANGELOG.md).

## MCP Server

Sentinel exposes itself as an MCP server over stdio ([ADR-011](docs/adr/011-sentinel-as-mcp-server.md)). It is not part of the demo.

| Tool | Description |
| ---- | ----------- |
| `sentinel_analyze` | Run the pipeline on the ticker's saved input to the approval gate. Returns `thread_id` + draft snapshot. |
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
