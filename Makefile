PYTHON := uv run python

MAP ?= maps/easy/01_linear_path.txt
MAP_TIERS := easy medium hard challenger

.PHONY: install run makespan run-all gui debug clean lint test benchmark

install:
	uv sync --group dev

run:
	$(PYTHON) -m src $(MAP)

makespan:
	$(PYTHON) -m src --makespan $(MAP)

run-all:
	@for dir in $(MAP_TIERS); do \
		for map in maps/$$dir/*.txt; do \
			echo "=== $$map ==="; \
			$(PYTHON) -m src --makespan $$map; \
		done; \
	done

gui:
	$(PYTHON) -m src --gui $(MAP)

debug:
	$(PYTHON) -m pdb -m src --debug $(MAP)

clean:
	rm -rf .venv .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name '*.egg-info' -exec rm -rf {} +

lint:
	uv run mypy src tests
	uv run flake8 src

test:
	uv run pytest tests || true

benchmark:
	uv run pytest tests/test_benchmarks.py -q
