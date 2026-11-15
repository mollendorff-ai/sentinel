# Security Policy

## Important context

Sentinel is a prototype, built with AI assistance, and not financial advice. Since 0.9.0 it fetches nothing from the web: it reads an earnings release saved in `inputs/`, sends it to an LLM (an AI in a chat through files, or an API provider with your key), and calls Forge, pinned by checksum, as its only calculator. It has no server of its own. Run it on your own machine or in a chat's sandbox, with API keys you can rotate, and do not deploy it where others can reach it.

## Supported versions

Only the latest release gets security fixes.

## Reporting a vulnerability

Please do not open a public issue for a security problem.

Email **<security@mollendorff.ai>** with:

- what you found and what it lets someone do,
- steps that reproduce it (the command and the input),
- the Sentinel version and your operating system.

You can also use GitHub's private vulnerability reporting, under the **Security** tab of this repository, if it is enabled.

Sentinel is a small project kept up on a best-effort basis. I aim to reply within 14 days, and I will tell you what I plan to do about the report. Please give me reasonable time to ship a fix before you share the details publicly. I am glad to credit you in the release notes if you want that.

## What is in scope

- Input handling: the ticker, the period and anything else that ends up in a file name or a path.
- The files Sentinel reads and writes: `inputs/`, `runs/`, `.sentinel/chat/` (prompts and answers) and `.sentinel/failed/` (failed runs).
- How API keys are loaded from `.env` and the environment, and anything that could leak them, including into LangSmith traces or a run's `llm/` folder.
- How Sentinel installs Forge (`scripts/install-forge.sh` and its checksum) and passes model output to it.

## What is not in scope

- Vulnerabilities in Forge: report those in [its repository](https://github.com/mollendorff-ai/forge).
- Text in a saved document that tries to steer the LLM. The prompt marks the document as data, and a run's figures are checked against `expected.yaml` and the filing's subtotals, but a new input is only as trustworthy as the person who saved and checked it.
- What the AI in a chat does with the access its sandbox gives it. The prompt tells it to touch only `runs/`, and nothing enforces that, so **a reviewer checks that a run's pull request changes only `runs/<TICKER>/<timestamp>/`** before merging it.
- Wrong figures or a poor analysis are bugs, not security problems: please open a normal issue for those.
