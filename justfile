# paprika — the local quality gate
#
# `just check` is what has to be green before anything is pushed.

uv := "uv"

# Show the available recipes
default:
    @just --list

# Sync the venv from the lockfile, dev group included
install:
    {{uv}} sync --all-groups

# Rewrite the tree with Black and Ruff's autofixes
format:
    {{uv}} run black src tests
    {{uv}} run ruff check --fix src tests

# Black --check and Ruff, no writes
lint:
    {{uv}} run black --check src tests
    {{uv}} run ruff check src tests

# mypy
typecheck:
    {{uv}} run mypy

# Vulture — dead code that lint does not see
deadcode:
    {{uv}} run vulture

# pytest, which also enforces the 80% coverage floor
test:
    {{uv}} run pytest

# Alias: the floor is enforced inside pytest
coverage-check: test

# pip-audit against the locked dependencies
audit:
    {{uv}} run pip-audit

# The full local quality gate
check: lint typecheck deadcode test

# Alias for check
checkit: check

# Rebuild the venv from scratch, then install
pristine: clean install

# Install the git hooks
hooks:
    {{uv}} run pre-commit install

# Remove build, test and type-check caches
clean:
    rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml .coverage
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
