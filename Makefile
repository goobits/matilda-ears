# Matilda Ears Development Makefile

.PHONY: help test test-summary test-diff test-sequential lint format type-check quality clean install dev

PY ?= python3

help: ## Show this help message
	@echo "Matilda Ears Development Commands:"
	@echo "==================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

test: ## Run all tests with auto-parallel
	@./scripts/test.py

test-summary: ## Run tests with YAML failure summary
	@./scripts/test.py --summary

test-diff: ## Compare test results vs last run
	@./scripts/test.py --diff=-1

test-sequential: ## Run tests sequentially (for debugging)
	@./scripts/test.py --sequential

test-formatting: ## Run Ears Tuner tests only
	@./scripts/test.py tests/ears_tuner/ --summary

lint: ## Run linting with ruff
	@echo "Running linter..."
	@$(PY) -c "import ruff" 2>/dev/null || (echo "ruff is not installed. Install dev deps: python3 -m pip install -e '.[dev]'"; exit 1)
	@$(PY) -m ruff check src/matilda_ears/ tests/

format: ## Format code with black
	@echo "Formatting code..."
	@$(PY) -c "import black" 2>/dev/null || (echo "black is not installed. Install dev deps: python3 -m pip install -e '.[dev]'"; exit 1)
	@$(PY) -m black src/matilda_ears/ tests/ --line-length 120

type-check: ## Run type checking with mypy
	@echo "Running type checker..."
	@$(PY) -c "import mypy" 2>/dev/null || (echo "mypy is not installed. Install dev deps: python3 -m pip install -e '.[dev]'"; exit 1)
	@$(PY) -m mypy src/matilda_ears/

quality: format lint type-check ## Run all code quality checks
	@echo "All quality checks completed!"

clean: ## Clean up build artifacts and cache
	@echo "Cleaning up..."
	@rm -rf __pycache__ .pytest_cache .mypy_cache .coverage htmlcov
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete

install: ## Install package with pipx
	@./scripts/setup.sh install

dev: ## Install in development mode
	@./scripts/setup.sh install --dev
