VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: all setup migrate run clean

all: setup run

$(VENV)/bin/activate:
	@echo "Creating virtual environment..."
	python3 -m venv $(VENV)
	@echo "Installing dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -e .
	@touch $(VENV)/bin/activate
	@echo "Setup complete."

setup: $(VENV)/bin/activate


run: migrate
	$(PYTHON) -m app.main

migrate:
	$(PYTHON) -m app.db.migrations.migrate

clean:
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} +

# Tests
test-up:
	docker compose -f tests/docker-compose.test.yml up -d

test-down:
	docker compose -f tests/docker-compose.test.yml down

test: test-up
	$(PYTHON) -m pytest tests/ -v
