# ADR 0003: Dependency Policy — Zero External Python Dependencies

## Status

Accepted

## Context

Ansible collections can depend on external Python packages (e.g., `requests`, `lxml`). However, external dependencies create installation friction, especially in restricted environments, execution environments (EE), and CI pipelines.

## Decision

**Zero external Python dependencies. Use only `ansible.module_utils.urls` and Python stdlib.**

Specifically:
- HTTP calls: `ansible.module_utils.urls.open_url()` (wraps urllib)
- XML parsing: `xml.etree.ElementTree` (stdlib)
- JSON handling: `json` (stdlib)
- No `requests`, no `lxml`, no `xmltodict`

## Rationale

- **Frictionless install**: `ansible-galaxy collection install voipnorm.roomos` is all you need
- **EE compatible**: No additional Python packages to bake into execution environments
- **CI friendly**: No pip install step before running playbooks
- **Smaller attack surface**: Fewer dependencies = fewer CVE risks

## Consequences

- `open_url()` is less ergonomic than `requests` but fully adequate for our use case
- `ElementTree` handles RoomOS XML responses well; no need for `lxml` xpath features
- If future modules need advanced XML features, we can reconsider for v1.1

## Trade-offs

- `open_url()` error messages are sometimes less descriptive — we wrap with our own error handling
- No connection pooling — each call opens a new connection (acceptable for task-by-task execution)
