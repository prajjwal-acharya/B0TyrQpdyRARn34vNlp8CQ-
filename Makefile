# =============================================================================
# Adaptive AI Document Intelligence Platform — Makefile
#
# Windows users: Run these commands inside WSL2, or install make via Chocolatey
# (choco install make) and run directly. Alternatively, use the equivalent
# `docker compose` commands listed in docs/setup-windows.md.
# =============================================================================

COMPOSE        = docker compose
COMPOSE_DEV    = docker compose -f docker-compose.yml -f docker-compose.dev.yml
API_CONTAINER  = api

.PHONY: up down dev logs migrate lint test setup clean help

## up: Start all services in detached mode
up:
	$(COMPOSE) up -d

## down: Stop all services (preserves volumes)
down:
	$(COMPOSE) down

## dev: Start with hot-reload volume mounts (development mode)
dev:
	$(COMPOSE_DEV) up

## logs: Tail logs from all services
logs:
	$(COMPOSE) logs -f

## migrate: Run Alembic migrations inside the api container
migrate:
	$(COMPOSE) exec $(API_CONTAINER) alembic upgrade head

## lint: Run ruff (lint + format check) and mypy
lint:
	ruff check .
	ruff format --check .
	mypy shared/

## test: Run the test suite with pytest
test:
	pytest

## setup: Copy .env.example to .env if .env does not already exist
setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo ".env created — open it and fill in your API keys before running 'make up'."; \
	else \
		echo ".env already exists, skipping copy."; \
	fi

## clean: Stop all services AND remove volumes (destructive — data will be lost)
clean:
	$(COMPOSE) down -v

## help: Show this help message
help:
	@grep -E '^## ' Makefile | sed 's/## //'
