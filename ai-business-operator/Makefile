COMPOSE := docker compose -f infra/docker-compose.yml
AGENT ?= research_agent

.PHONY: help up down logs migrate psql redis test lint fmt worker browser-agent frontend clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Start postgres, redis, backend and a worker
	$(COMPOSE) up -d --build

down: ## Stop the stack
	$(COMPOSE) down

logs: ## Tail all service logs
	$(COMPOSE) logs -f

migrate: ## Apply the initial schema to the running database
	$(COMPOSE) exec -T postgres psql -U aibo -d aibo < infra/sql/001_init.sql

psql: ## Open a database shell
	$(COMPOSE) exec postgres psql -U aibo -d aibo

redis: ## Open a redis shell
	$(COMPOSE) exec redis redis-cli

test: ## Run the Python test suite
	cd backend && python -m pytest -q

lint: ## Lint and type-check
	ruff check backend agents browser_agent vector_memory
	mypy backend/app

fmt: ## Format Python sources
	ruff format backend agents browser_agent vector_memory

worker: ## Run a single agent worker in the foreground (AGENT=copy_agent)
	python -m agents.worker --agent $(AGENT)

browser-agent: ## Run the browser agent worker in the foreground
	python -m browser_agent.agent

frontend: ## Run the Next.js dashboard
	cd frontend && npm run dev

clean: ## Remove containers, volumes and caches
	$(COMPOSE) down -v
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache artifacts
