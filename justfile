
# t
install:
	uv sync

lint:
   @uv run ruff check --select I --fix src

fmt:
    uv run ruff check --fix-only src
    uv run ruff format ./src

check:
    uv run ruff check ./src
    uv run ruff format --check ./src
    uv run mypy ./src

test:
   @uv run pytest tests/*.py

build:
    @uv build --wheel

clean-build:
    @rm -rf build dist

clean-cache:
    @rm -rf .mypy_cache .pytest_cache .ruff_cache ./src/**/__pycache__

release-tag:
    @uv run --no-project ./scripts/release_script.py release-tag

update-pyproject-version:
    uv run --no-project ./scripts/release_script.py update-pyproject-version

