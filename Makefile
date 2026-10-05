.PHONY: install check lint typecheck test test-all gate clean

UV ?= uv
STAGE ?= 1

install:
	$(UV) sync

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

typecheck:
	$(UV) run mypy

test:
	$(UV) run pytest -m "not model and not slow and not gate"

check: lint typecheck test

test-all:
	$(UV) run pytest

gate:
	$(UV) run mastrace gate --stage $(STAGE) $(GATE_ARGS)

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build logs
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
