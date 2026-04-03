.PHONY: help install dev-install up down logs migrate test lint format clean \
        api dashboard worker research-run generate-sample-data

# ─────────────────────────────────────────────────────────────────
# Variables
# ─────────────────────────────────────────────────────────────────
PYTHON      := python3
PIP         := pip
ALEMBIC     := alembic
PYTEST      := pytest
UVICORN     := uvicorn
STREAMLIT   := streamlit

# ─────────────────────────────────────────────────────────────────
# Help
# ─────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Alpha Platform — Developer Commands"
	@echo "  ───────────────────────────────────"
	@echo "  make install            Install production dependencies"
	@echo "  make dev-install        Install dev + production dependencies"
	@echo "  make up                 Start all Docker services"
	@echo "  make down               Stop all Docker services"
	@echo "  make logs               Tail Docker logs"
	@echo "  make migrate            Run Alembic migrations"
	@echo "  make migrate-create m=  Create new Alembic migration"
	@echo "  make api                Run FastAPI locally (no Docker)"
	@echo "  make dashboard          Run Streamlit dashboard locally"
	@echo "  make test               Run all tests"
	@echo "  make test-unit          Run unit tests only"
	@echo "  make test-cov           Run tests with coverage report"
	@echo "  make lint               Run ruff linter"
	@echo "  make format             Auto-format with black"
	@echo "  make research-run       Run a full research pipeline (CSV data required)"
	@echo "  make generate-data      Generate synthetic sample CSV data"
	@echo "  make clean              Remove __pycache__ and .pyc files"
	@echo ""

# ─────────────────────────────────────────────────────────────────
# Install
# ─────────────────────────────────────────────────────────────────
install:
	$(PIP) install -e .

dev-install:
	$(PIP) install -e ".[dev]"

# ─────────────────────────────────────────────────────────────────
# Docker
# ─────────────────────────────────────────────────────────────────
up:
	docker compose up -d --build
	@echo "Services started. API: http://localhost:8000 | Dashboard: http://localhost:8501"

down:
	docker compose down

logs:
	docker compose logs -f

restart:
	docker compose restart

# ─────────────────────────────────────────────────────────────────
# Database / Migrations
# ─────────────────────────────────────────────────────────────────
migrate:
	$(ALEMBIC) upgrade head

migrate-create:
	$(ALEMBIC) revision --autogenerate -m "$(m)"

migrate-down:
	$(ALEMBIC) downgrade -1

migrate-history:
	$(ALEMBIC) history --verbose

# ─────────────────────────────────────────────────────────────────
# Local services (no Docker)
# ─────────────────────────────────────────────────────────────────
api:
	$(UVICORN) app.api.main:app --host 0.0.0.0 --port 8000 --reload

dashboard:
	$(STREAMLIT) run app/dashboard/app.py --server.port 8501

worker:
	celery -A app.workers.celery_app worker --loglevel=info --concurrency=2

# ─────────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────────
test:
	$(PYTEST)

test-unit:
	$(PYTEST) tests/unit/

test-integration:
	$(PYTEST) tests/integration/

test-cov:
	$(PYTEST) --cov=app --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

# ─────────────────────────────────────────────────────────────────
# Code quality
# ─────────────────────────────────────────────────────────────────
lint:
	ruff check app/ tests/

format:
	black app/ tests/ scripts/

typecheck:
	mypy app/ --ignore-missing-imports

# ─────────────────────────────────────────────────────────────────
# Research pipeline
# ─────────────────────────────────────────────────────────────────
research-run:
	$(PYTHON) scripts/run_research.py

generate-data:
	$(PYTHON) scripts/generate_sample_data.py

# ─────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "*.pyo" -delete 2>/dev/null || true
	find . -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned."

dirs:
	mkdir -p data/historical data/results data/state logs
