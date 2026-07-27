.PHONY: setup test lint check validate-artifacts clean-generated

setup:
	uv sync --dev

test:
	uv run pytest

lint:
	uv run ruff check ait tests

check: lint test

validate-artifacts:
	uv run python -m ait.artifacts results

clean-generated:
	rm -f results/derived/*.json results/generated/*.tex
