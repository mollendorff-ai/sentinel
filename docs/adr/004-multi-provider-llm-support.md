# ADR-004: Multi-provider LLM support via env-var factory

**Status:** Accepted
**Date:** 2026-02-22

## Context

Sentinel hardcodes `ChatAnthropic` in every agent node. This creates two problems:

1. **Demo cost.** Each run uses Claude Sonnet ($3/$15 per MTok). For screencast recordings and iterative testing, free-tier providers (Google Gemini 2.5 Flash) would eliminate costs entirely.
2. **Vendor lock-in perception.** A portfolio project demonstrating LangGraph should showcase model-agnostic design -- the orchestration layer is the value, not any single LLM provider.

Three approaches were considered:

1. **Constructor injection** -- pass the LLM instance into each node function. Clean but changes every node signature and requires graph-level wiring changes.
2. **Config object** -- a `SentinelConfig` dataclass threaded through state. Flexible but over-engineered for a single setting.
3. **Env-var factory** -- a `get_llm()` function that reads `SENTINEL_LLM_PROVIDER` and `SENTINEL_LLM_MODEL` from the environment.

## Decision

Env-var factory (`sentinel.llm.get_llm()`). Agents call `get_llm()` instead of constructing a provider-specific class directly.

## Rationale

**12-factor config.** Environment variables are the standard mechanism for deployment-time configuration. No code changes needed to switch providers -- just set an env var.

**Minimal diff.** Each agent changes exactly one import and one line of code. No signature changes, no state schema changes, no graph rewiring.

**Lazy imports.** Provider packages (`langchain-openai`, `langchain-google-genai`, `langchain-groq`) are optional dependencies. The factory only imports the selected provider, so the others need not be installed.

**Test-friendly.** Tests patch `get_llm` at the import location (same pattern as before, just a different name). The factory itself is tested independently with mocked imports.

## Supported Providers

| Provider | Package | Default Model |
| ---------- | --------- | --------------- |
| `anthropic` (default) | `langchain-anthropic` | `claude-sonnet-4-20250514` |
| `openai` | `langchain-openai` | `gpt-4o-mini` |
| `google` | `langchain-google-genai` | `gemini-2.5-flash` |
| `groq` | `langchain-groq` | `llama-3.3-70b-versatile` |

## Consequences

- Agents are decoupled from any specific LLM provider
- `langchain-anthropic` remains a required dependency (default provider)
- Other providers are optional extras (`pip install sentinel[google]`)
- Provider-specific kwargs (e.g. Google's `max_output_tokens` vs `max_tokens`) are handled inside the factory
- Adding a new provider requires adding one entry to `PROVIDER_DEFAULTS` and `_CLASS_NAMES`
