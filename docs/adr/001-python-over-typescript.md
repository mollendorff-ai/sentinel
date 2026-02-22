# ADR-001: Python over TypeScript for LangGraph orchestration

**Status:** Accepted
**Date:** 2026-02-21

## Context

Sentinel uses LangGraph for multi-agent orchestration. The LangChain/LangGraph ecosystem supports both Python and TypeScript (LangChain.js / LangGraph.js). We needed to choose one.

## Decision

Python.

## Rationale

**Ecosystem maturity favors Python.** LangGraph reached stable 1.0 in late 2025 on Python first. LangSmith tracing, CrewAI, AutoGen, and the broader agentic AI toolchain (vector DBs, RAG frameworks, MLOps) are Python-native. The LangChain team itself recommends LangGraph (Python) over LangChain for agentic work.

**Industry adoption.** Python dominates agentic AI in production. LangGraph.js exists but has less community support, fewer examples, and lags behind the Python SDK in features.

## Alternatives considered

- **TypeScript/LangChain.js** — Growing ecosystem but less mature. TypeScript is strong for web frontends but secondary for AI/agent orchestration.

## Consequences

- All Sentinel code is Python (3.11+)
- Dependencies: langgraph, langchain, langsmith
- forge and ref remain Rust CLIs, called via subprocess
