# ADR-012: Sentinel as Forge's AI-pipeline demonstration

**Status:** Accepted, amended by [ADR-013](013-run-in-a-chat.md) and [ADR-014](014-check-the-formulas-and-keep-only-the-demo.md) on 2026-11-15
**Date:** 2026-11-15
**Supersedes:** [ADR-009](009-qdrant-rag-historical-earnings.md) (Qdrant history)
**Amends:** [ADR-005](005-ref-mcp-over-cli-subprocess.md) (Ref is no longer used in a demo run), [ADR-006](006-five-agent-pipeline.md) (the Retriever reads files, not Qdrant)

> **2026-11-15:** amended by ADR-013. The demo runs in an AI chat, with the chat as the LLM,
> instead of unattended in GitHub Actions with an API key (decisions 4 and 5 below).
>
> **2026-11-15:** amended by [ADR-014](014-check-the-formulas-and-keep-only-the-demo.md): the `--hitl` gate and the MCP server, which this ADR kept, are removed.

## Context

Sentinel was built as an earnings-analysis product: give it a ticker, it scrapes two live
Macrotrends pages, an LLM extracts the figures, Forge calculates, and an LLM writes a brief.
Version 0.8.1 made that path run, but it has never been run end to end by the maintainer, it
depends on a site whose terms restrict automated access, and a live page gives a different input
on every run, so no run can be checked or repeated.

Forge's [docs/WORKFLOWS.md](https://github.com/mollendorff-ai/forge/blob/main/docs/WORKFLOWS.md)
describes Forge in an AI pipeline: an agent reads a document and writes a model, Forge validates
and calculates it, the agent reads Forge's numbers rather than its own arithmetic, and a person
reviews the result as a pull request. Every step is a Forge command that works, but no whole
pipeline has run. Forge's roadmap item T2-PIPELINE-DEMO names Sentinel as the demonstration. Its
acceptance criterion: Sentinel runs end to end on a known input with no person in the loop, its
models and results are in git, and WORKFLOWS.md links to it.

The maintainer works from an iPhone and has no machine to run it on, so the demonstration has to
run in GitHub Actions.

## Decision

Sentinel's goal is to be that demonstration. It is not an earnings product and gives no
investment advice. Each part of it is kept only if it serves the demonstration.

1. **A saved, known input.** A demo run reads a company's quarterly results from a file in the
   repository (`inputs/<TICKER>/<period>/`), not from the web. The first input is one quarter of
   a public company's earnings release as filed with the SEC (Form 8-K, Exhibit 99.1), a US
   government source with no terms against reuse. Live Macrotrends fetching is removed.
2. **Figures checked outside the LLM.** Each input has an `expected.yaml` with the headline
   figures (revenue, cost of revenue, operating expenses, net income) typed by a person from the
   filing. A run fails when the LLM's extraction differs from it. This is the check of the one
   step Forge cannot check: whether the right number was read from the page.
3. **Forge is the only calculator.** The LLM writes the model in the current Forge model format,
   Forge validates and calculates it, and every number in the brief comes from Forge's reply.
   Forge is pinned to a release and installed from its release binary, verified against the
   release's `checksums.txt`, never built or piped into a shell.
4. **Unattended, in GitHub Actions.** A workflow, started by hand (`workflow_dispatch`), runs the
   pipeline with the LLM key as a repository secret and no prompt or approval step.
5. **The record is git, the review is a pull request.** The workflow commits the run's input,
   model, Forge results and brief to a branch and opens a pull request. A person reviews a diff
   of figures, formulas and results, as in WORKFLOWS.md. This pull request is the human review
   of the demo; the `--hitl` gate and the MCP server stay as they are but are not part of it.
6. **No vector store.** History comes from earlier runs, which are already files in git. The
   Retriever reads the previous runs' results for the ticker from the repository. Qdrant and
   `qdrant-client` are removed.
7. **What Forge made hard is recorded.** Every Forge message, option or output a program had to
   work around is written down and reported to Forge as a roadmap item, which is half the point
   of the demonstration.

## Consequences

- One run can be repeated and checked: the same input, figures compared with `expected.yaml`,
  numbers from Forge. Only the wording of the brief changes from run to run.
- Sentinel no longer analyses any ticker on demand. Adding a company means adding its filing and
  its `expected.yaml`, a reviewed change.
- The risk of prompt injection through a fetched page goes away for demo runs, since the input is
  a committed file a person reviewed. Most of the old 0.9.0 security sprint was about live input
  and a long-running MCP server; it is replaced by the demo milestone, and the items that still
  apply move to the backlog.
- Ref is no longer needed to run Sentinel. It may come back later as the way to fetch a new
  filing, which then goes through review like any other input.
- Existing `.sentinel/qdrant` data is not read.

## Alternatives considered

- **Keep live Macrotrends input.** Rejected: the terms restrict automated access, and a run that
  changes with the page cannot be checked or repeated.
- **Keep Qdrant for history.** Rejected: since 0.8.1 it is looked up by ticker with a placeholder
  vector, so it is a key-value store, and earlier runs are already files in git.
- **A demo example inside the Forge repository.** Rejected by the maintainer (Forge roadmap,
  2026-11-15): Sentinel already has the agents and shows Forge used by a separate program, as a
  user would.
- **Run on the maintainer's computer.** Not possible from an iPhone; Actions also makes every run
  visible.

## Addendum (2026-11-15, 0.9.0): how the first input was saved

SEC EDGAR refuses automated requests that do not declare who is asking: its fair-access policy
asks for a user agent with a name and a contact email. Ref 1.8.4 was refused ("Undeclared
Automated Tool") because it has no option to set one. The first input was downloaded once with
`curl` and the user agent `Mollendorff AI Sentinel security@mollendorff.ai`, the contact already
published in SECURITY.md, approved by the maintainer. The original HTML is kept beside the
Markdown made from it (`scripts/html_to_markdown.py`), with both checksums in `source.yaml`, so
anyone can compare it with the SEC's copy. A user-agent option is a finding to report to Ref.
