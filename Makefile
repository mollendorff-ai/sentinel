.DEFAULT_GOAL := help
SHELL := /bin/bash

VENV   := .venv
PYTHON := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip
TICKER ?= AAPL

# ── Setup ─────────────────────────────────────────────────────────

.PHONY: setup
setup: $(VENV)/bin/activate .env ## Create venv, install deps, copy .env
	@echo "✔ Ready — activate with: source $(VENV)/bin/activate"

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

.env:
	cp .env.example .env
	@echo "⚠ Created .env from .env.example — edit it with your API keys"

# ── Quality gates ─────────────────────────────────────────────────

.PHONY: lint
lint: ## Run ruff format check + lint (ALL rules)
	$(VENV)/bin/ruff format --check .
	$(VENV)/bin/ruff check --select ALL .

.PHONY: test
test: ## Run full test suite with coverage (100% required)
	$(PYTHON) -m pytest --cov=src/sentinel --cov-fail-under=100 -q

.PHONY: check
check: lint test ## Run all quality gates (lint + test)

# ── Demo ──────────────────────────────────────────────────────────

.PHONY: demo
demo: ## Run full 5-agent analysis (TICKER="AAPL" or "AAPL MSFT")
	$(PYTHON) -m sentinel $(TICKER)

.PHONY: demo-quick
demo-quick: ## Run quick 3-agent analysis (skip risk + scenarios)
	$(PYTHON) -m sentinel --quick $(TICKER)

# ── Cleanup ───────────────────────────────────────────────────────

.PHONY: clean
clean: ## Remove build artifacts and caches
	rm -rf __pycache__ .pytest_cache .coverage htmlcov .ruff_cache
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -not -path "./.venv/*" -delete 2>/dev/null || true

.PHONY: clean-all
clean-all: clean ## Remove everything including venv
	rm -rf $(VENV)

# ── Help ──────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
