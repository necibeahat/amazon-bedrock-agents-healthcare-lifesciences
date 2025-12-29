# Makefile for Agentic Pharmaceutical Pipeline

.PHONY: help install install-dev test test-basic lint format clean docker-up docker-down db-init db-test

# Default target
help:
	@echo "Available commands:"
	@echo "  install      - Install production dependencies"
	@echo "  install-dev  - Install development dependencies"
	@echo "  test         - Run all tests"
	@echo "  test-basic   - Run basic structure tests"
	@echo "  lint         - Run linting checks"
	@echo "  format       - Format code"
	@echo "  clean        - Clean up temporary files"
	@echo "  docker-up    - Start Docker services"
	@echo "  docker-down  - Stop Docker services"
	@echo "  db-init      - Initialize databases"
	@echo "  db-test      - Test database connections"

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

# Testing
test:
	pytest tests/ -v --cov=src --cov-report=term-missing

test-basic:
	python3 tests/test_basic_structure.py

# Code quality
lint:
	flake8 src tests
	mypy src

format:
	black src tests
	isort src tests

# Cleanup
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/

# Docker services
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

# Database management
db-init:
	python -m src.cli db init

db-test:
	python -m src.cli db test

db-status:
	python -m src.cli db status

# Development
dev: docker-up
	@echo "Development environment started!"
	@echo "Services available:"
	@echo "  - PostgreSQL: localhost:5432"
	@echo "  - MongoDB: localhost:27017"
	@echo "  - Redis: localhost:6379"
	@echo "  - Jaeger UI: http://localhost:16686"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Grafana: http://localhost:3000"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Run 'make db-init' to initialize databases"
	@echo "  2. Run 'make test-basic' to verify setup"

# Configuration
config-show:
	python -m src.cli config show

config-validate:
	python -m src.cli config validate

# Agents
agents-list:
	python -m src.cli agents list

# Version
version:
	python -m src.cli version