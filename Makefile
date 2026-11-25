.PHONY: sync test lint fmt clean

sync:
	uv sync

test:                       ## 모델 호출 0회로 전부 돈다
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

clean:
	rm -rf .pytest_cache .ruff_cache dist build
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
