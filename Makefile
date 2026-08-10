# Matilda Ears Development Makefile

.PHONY: help test test-ci test-summary test-diff test-sequential
.PHONY: lint format format-check type-check security-check complexity-check quality check
.PHONY: clean install dev

PY ?= python3

help: ## Show this help message
	@echo "Matilda Ears Development Commands:"
	@echo "==================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

test: ## Run all tests with auto-parallel
	@./scripts/test.py

test-ci: ## Run deterministic tests with coverage enforcement
	@./scripts/test.py --sequential --no-track --coverage

test-summary: ## Run tests with YAML failure summary
	@./scripts/test.py --summary

test-diff: ## Compare test results vs last run
	@./scripts/test.py --diff=-1

test-sequential: ## Run tests sequentially (for debugging)
	@./scripts/test.py --sequential

lint: ## Run linting with ruff
	@echo "Running linter..."
	@$(PY) -c "import ruff" 2>/dev/null || (echo "ruff is not installed. Install dev deps: python3 -m pip install -e '.[dev]'"; exit 1)
	@$(PY) -m ruff check .

format: ## Format code with black
	@echo "Formatting code..."
	@$(PY) -c "import black" 2>/dev/null || (echo "black is not installed. Install dev deps: python3 -m pip install -e '.[dev]'"; exit 1)
	@$(PY) -m black .

format-check: ## Check formatting (non-mutating)
	@echo "Checking format..."
	@$(PY) -c "import black" 2>/dev/null || (echo "black is not installed. Install dev deps: python3 -m pip install -e '.[dev]'"; exit 1)
	@$(PY) -m black --check .

type-check: ## Run type checking with mypy
	@echo "Running type checker..."
	@$(PY) -c "import mypy" 2>/dev/null || (echo "mypy is not installed. Install dev deps: python3 -m pip install -e '.[dev]'"; exit 1)
	@$(PY) -m mypy src/

security-check: ## Scan owned source for medium and high severity issues
	@echo "Running security scan..."
	@$(PY) -c "import bandit" 2>/dev/null || (echo "bandit is not installed. Install dev deps: python3 -m pip install -e '.[dev]'"; exit 1)
	@$(PY) -m bandit -q -r src/matilda_ears -c pyproject.toml -ll

complexity-check: ## Enforce complexity limits on refactored runtime paths
	@echo "Checking hotspot complexity..."
	@$(PY) -m ruff check \
		src/matilda_ears/audio/capture.py \
		src/matilda_ears/core/auth.py \
		src/matilda_ears/core/token_store.py \
		src/matilda_ears/modes/base_mode.py \
		src/matilda_ears/modes/conversation.py \
		src/matilda_ears/modes/listen_once.py \
		src/matilda_ears/transcription/client/unified.py \
		src/matilda_ears/transcription/server/internal/audio_utils.py \
		src/matilda_ears/transcription/server/internal/session_registry.py \
		src/matilda_ears/wake_word/detector.py \
		--select C901,PLR0911,PLR0912,PLR0915

quality: format-check lint type-check security-check complexity-check ## Run all code quality checks
	@echo "All quality checks completed!"

check: quality test-ci ## Run the complete CI-equivalent verification suite

clean: ## Clean up build artifacts and cache
	@echo "Cleaning up..."
	@rm -rf __pycache__ .pytest_cache .mypy_cache .coverage htmlcov
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete

install: ## Install package from this checkout
	@./scripts/setup.sh install --dev

dev: ## Install in development mode
	@./scripts/setup.sh install --dev
