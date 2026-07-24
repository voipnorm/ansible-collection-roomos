# Development Guide

## Prerequisites

- Python >= 3.10
- Docker (for `ansible-test` sandboxed testing)
- Git

## Setup

```bash
git clone https://github.com/voipnorm/ansible-collection-roomos.git
cd ansible-collection-roomos

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
```

## Development commands

```bash
make lint          # Run pre-commit hooks (ruff, yamllint)
make sanity        # Run ansible-test sanity in Docker
make unit          # Run ansible-test units in Docker
make build         # Build collection tarball
make install-dev   # Install latest build locally
make clean         # Remove build artifacts
```

## Running tests locally without Docker

For faster iteration, you can run unit tests directly with pytest. The collection must be installed or symlinked into the expected Ansible collection path:

```bash
# Symlink for local development
mkdir -p ~/.ansible/collections/ansible_collections/voipnorm
ln -sf $(pwd) ~/.ansible/collections/ansible_collections/voipnorm/roomos

# Run tests
python -m pytest tests/unit/ -v
```

## Architecture

See [docs/adr/](adr/) for architecture decision records:
- [ADR 0001](adr/0001-execution-model.md) — Controller-side modules
- [ADR 0002](adr/0002-transport-strategy.md) — Cloud + Local HTTP transport
- [ADR 0003](adr/0003-dependency-policy.md) — Zero external dependencies

## Branch protection (recommended)

- Require PRs for `main`
- Require passing CI checks
- Require at least 1 review approval
- No force pushes to `main`

## Release process

1. Update `version` in `galaxy.yml`
2. Add changelog fragment to `changelogs/fragments/`
3. Merge to `main`
4. Tag: `git tag v0.1.0 && git push --tags`
5. Release workflow publishes to Galaxy automatically
