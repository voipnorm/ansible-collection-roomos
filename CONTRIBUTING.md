# Contributing to voipnorm.roomos

Thank you for your interest in contributing! This document covers the development workflow.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/voipnorm/ansible-collection-roomos.git
cd ansible-collection-roomos

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dev dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

## Development Workflow

```bash
# Run linters
make lint

# Run sanity tests
make sanity

# Run unit tests
make unit

# Build the collection
make build

# Install locally for testing
make install-dev
```

## Code Style

- Python code follows PEP 8, enforced by `ruff`
- YAML files follow `.yamllint` rules
- All modules must include `DOCUMENTATION`, `EXAMPLES`, and `RETURN` strings
- Use `from __future__ import absolute_import, division, print_function` in all Python files
- Add `__metaclass__ = type` after future imports

## Pull Request Process

1. Fork the repo and create a feature branch from `main`
2. Write tests for new functionality
3. Ensure `make lint`, `make sanity`, and `make unit` pass
4. Update documentation if needed
5. Submit a PR with a clear description of the change

## Test Requirements

- All new modules must have unit tests with ≥ 90% coverage
- Transport changes must include mocked tests for both cloud and local
- Integration tests (against real devices) are welcome but not required for PRs

## Reporting Issues

Use [GitHub Issues](https://github.com/voipnorm/ansible-collection-roomos/issues) with the appropriate template.
