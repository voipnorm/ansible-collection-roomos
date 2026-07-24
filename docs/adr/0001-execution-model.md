# ADR 0001: Execution Model — Controller-Side Modules

## Status

Accepted

## Context

Ansible supports multiple execution models for device modules:
1. **Controller-side modules** — Module runs on the Ansible controller, makes HTTP/API calls to the device
2. **httpapi connection plugin** — Ansible manages the persistent connection, modules use it
3. **On-device execution** — Module runs directly on the target device

RoomOS devices cannot run Python, which rules out option 3. Between options 1 and 2, we need to choose based on complexity, cloud+local dual-transport needs, and v1 scope.

## Decision

**Use controller-side modules for v1.**

Each module (`roomos_command`, `roomos_config`, `roomos_status`) receives connection parameters as arguments and makes HTTP calls using `ansible.module_utils.urls.open_url()`.

## Rationale

- **Simpler**: No connection plugin to write, test, and maintain
- **Dual transport**: Both cloud (Webex REST) and local (HTTP XML) are just different URL/auth patterns — easier to handle inside the module
- **Zero dependencies**: No httpapi plugin, no persistent connection setup
- **Faster to ship**: Reduces Gate 0→Gate 4 by estimated 2–3 days

## Consequences

- Each task opens its own HTTP connection (no connection reuse across tasks)
- Users must pass auth params on every task (mitigated by inventory variable fallbacks)
- Playbooks targeting many devices may be slightly slower than httpapi (acceptable for v1 fleet sizes)

## Future

An `httpapi` connection plugin is planned for v1.1. This will enable `connection: httpapi` with persistent connections. The internal transport interface (`RoomOSTransport` ABC) is designed to make this migration non-breaking — modules will detect connection type and delegate accordingly.
