PYTHON := uv run python

MAP ?= maps/example.map

.PHONY: install run debug clean lint

install:
	uv sync --group dev

run:
	$(PYTHON) -m src $(MAP)

debug:
	$(PYTHON) -X dev -m src --debug $(MAP)

clean:
	rm -rf .venv .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name '*.egg-info' -exec rm -rf {} +

lint:
	uv run mypy src
	uv run flake8 src
