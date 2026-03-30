.PHONY: help install dev test lint format clean docker-up docker-down migrate seed

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	@echo "Installing Python dependencies..."
	uv sync
	@echo "Installing frontend dependencies..."
	cd src/frontend && npm install
	@echo "Installing pre-commit hooks..."
	uv run pre-commit install

dev: ## Start development servers
	@echo "Starting backend and frontend..."
	cd src/frontend && npm run dev &
	uvicorn src.backend.main:app --reload --port 8000

test: ## Run all tests
	@echo "Running Python tests..."
	uv run pytest --cov=src/backend --cov-report=html
	@echo "Running frontend tests..."
	cd src/frontend && npm run test

test-backend: ## Run backend tests only
	uv run pytest --cov=src/backend --cov-report=html

test-frontend: ## Run frontend tests only
	cd src/frontend && npm run test

lint: ## Run linters
	@echo "Linting Python code..."
	uv run ruff check src/backend/
	uv run mypy src/backend/
	@echo "Linting frontend code..."
	cd src/frontend && npm run lint

format: ## Format all code
	@echo "Formatting Python code..."
	uv run black src/backend/
	uv run ruff check --fix src/backend/
	@echo "Formatting frontend code..."
	cd src/frontend && npx prettier --write "src/**/*.{ts,tsx,js,jsx,json,css}"

format-backend: ## Format backend code only
	uv run black src/backend/
	uv run ruff check --fix src/backend/

format-frontend: ## Format frontend code only
	cd src/frontend && npx prettier --write "src/**/*.{ts,tsx,js,jsx,json,css}"

clean: ## Clean up build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	rm -rf .coverage htmlcov/
	rm -rf src/frontend/dist/
	rm -rf src/frontend/node_modules/.cache/

docker-up: ## Start Docker containers
	docker-compose up -d

docker-down: ## Stop Docker containers
	docker-compose down

docker-build: ## Build Docker containers
	docker-compose build

migrate: ## Run database migrations
	uv run alembic upgrade head

migrate-create: ## Create a new migration
	@read -p "Enter migration message: " msg; \
	uv run alembic revision --autogenerate -m "$$msg"

seed: ## Seed the database with initial data
	uv run python -m src.backend.scripts.seed_db

backend: ## Run backend server only
	uvicorn src.backend.main:app --reload --port 8000

frontend: ## Run frontend server only
	cd src/frontend && npm run dev

check: lint test ## Run linters and tests

pre-commit: ## Run pre-commit on all files
	uv run pre-commit run --all-files

install-pre-commit: ## Install pre-commit hooks
	uv run pre-commit install

update-deps: ## Update all dependencies
	@echo "Updating Python dependencies..."
	uv lock --upgrade
	@echo "Updating frontend dependencies..."
	cd src/frontend && npm update

health: ## Check backend health
	curl -f http://localhost:8000/health || exit 1

logs: ## Show Docker logs
	docker-compose logs -f

psql: ## Connect to PostgreSQL database (if using Docker)
	docker-compose exec postgres psql -U postgres -d polygod

redis-cli: ## Connect to Redis (if using Docker)
	docker-compose exec redis redis-cli

setup: install migrate ## Full project setup

ci: lint test ## CI pipeline (lint + test)
