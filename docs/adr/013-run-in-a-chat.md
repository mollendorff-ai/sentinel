# ADR-013: The demo runs in an AI chat, with the chat as the LLM

**Status:** Accepted
**Date:** 2026-11-15
**Amends:** [ADR-012](012-sentinel-as-forge-demo.md), decision 4 (unattended in GitHub Actions) and the part of decision 5 about the workflow opening the pull request

## Context

ADR-012 had the demo run unattended in GitHub Actions, with an LLM API key as a repository secret. An API key is billed on its own, separately from a Claude subscription, and the maintainer, who already pays for a Max plan, decided not to add that cost.

An AI chat that can run commands (Claude Code, or a Claude chat with code execution) already has what a run needs: a Linux sandbox with Python, the network to install Sentinel and the pinned Forge, and a model that can read a filing and write YAML. Forge's [docs/WORKFLOWS.md](https://github.com/mollendorff-ai/forge/blob/main/docs/WORKFLOWS.md) describes this as its second workflow, a person with an AI in a chat, and [docs/PROMPTS.md](https://github.com/mollendorff-ai/forge/blob/main/docs/PROMPTS.md) shows how such prompts are written and tested.

## Decision

1. **The chat is the LLM.** A new provider, `SENTINEL_LLM_PROVIDER=chat`, calls no API. Each LLM step (extract the figures, write the model, write the brief) writes Sentinel's own prompt to `.sentinel/chat/<role>-<hash>.prompt.md`, and the run stops with exit status 3 until the answer file beside it is written. The AI in the chat answers and runs the same command again; answers already written are reused, so each run gets one step further. A prompt is named by a hash of its text, so an answer is reused only for exactly the prompt it answered.
2. **Everything else is unchanged.** Sentinel's code still does the rest: the expected-figure check, Forge's validation and calculation, risk and scenarios, history and the run folder. The prompts still say to copy numbers, never to calculate them, and the expected-figure check and Forge still catch a misread or a wrong sum.
3. **The transcript is part of the record.** A finished run keeps every prompt and answer in `runs/<TICKER>/<timestamp>/llm/`, so a reviewer sees exactly what the LLM was asked and said.
4. **The check of `expected.yaml` moves into the CLI.** `python -m sentinel` refuses an input whose `expected.yaml` says `checked: false`, unless it is given `--allow-unchecked`, and the run summary says which.
5. **A tested prompt starts a run.** The README holds the prompt to paste into a chat. It installs Sentinel and the pinned Forge, runs the loop, prints the summary, and opens a pull request with the run if the chat can push, or prints the files if not.
6. **The GitHub Actions demo workflow is removed.** It could not run without a key. It is in git history if a key is ever added. CI is unchanged: it needs no key.

## Consequences

- A run costs nothing beyond the subscription the maintainer already has.
- A person starts each run by pasting the prompt, and nothing in the loop needs them. Forge's roadmap item T2-PIPELINE-DEMO asks for "no person in the loop"; that holds for the run, but the trigger is a person in a chat, not a schedule, and its wording should say so.
- The LLM is whichever model the chat uses, recorded only by the chat. The transcript in `llm/` records what it was asked and what it answered.
- The AI in the chat could do more than answer: edit `inputs/`, change the code, or calculate a number itself. The prompt forbids it, and the review catches it: the diff of a run's pull request touches only `runs/`, and its figures are checked against `expected.yaml` and its results come from Forge.

## Alternatives considered

- **Keep GitHub Actions with an API key.** Rejected by the maintainer on cost.
- **Have the chat do the whole analysis without Sentinel.** Rejected: that is Forge's own PROMPTS.md. The point of Sentinel is a program that drives Forge, with its checks in code.
- **Answer the prompts through an MCP server in the chat.** More moving parts for the same result; files work in any chat that can run commands.
