# Security Policy

## Important context

Sentinel is a prototype, built with AI assistance, and not financial advice. It sends text from web pages to an LLM provider and calls Forge and Ref as tools. Run it on your own machine with API keys you can rotate, and do not deploy it where others can reach it.

## Supported versions

Only the latest release gets security fixes.

## Reporting a vulnerability

Please do not open a public issue for a security problem.

Email **security@mollendorff.ai** with:

- what you found and what it lets someone do,
- steps that reproduce it (the command, the ticker or the MCP call),
- the Sentinel version and your operating system.

You can also use GitHub's private vulnerability reporting, under the **Security** tab of this repository, if it is enabled.

Sentinel is a small project kept up on a best-effort basis. I aim to reply within 14 days, and I will tell you what I plan to do about the report. Please give me reasonable time to ship a fix before you share the details publicly. I am glad to credit you in the release notes if you want that.

## What is in scope

- Input handling: the ticker and anything else that ends up in a file name, a path or a command.
- The files Sentinel writes (the output folder, the SQLite checkpoint and the local Qdrant folder).
- How API keys are loaded from `.env` and the environment, and anything that could leak them, including into LangSmith traces.
- The MCP server (`sentinel_analyze` and `sentinel_resume`).
- How Sentinel passes model output to Forge and Ref.

## What is not in scope

- Vulnerabilities in Forge or Ref: report those in their own repositories.
- Text on a web page that tries to steer the LLM. Sentinel reads earnings pages and cannot tell which text is an instruction, so treat its figures as unverified and check them against the source.
- Wrong figures or a poor analysis are bugs, not security problems: please open a normal issue for those.
