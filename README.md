# Ansible Collection: voipnorm.roomos

[![CI](https://github.com/voipnorm/ansible-collection-roomos/actions/workflows/ci.yml/badge.svg)](https://github.com/voipnorm/ansible-collection-roomos/actions/workflows/ci.yml)
[![Galaxy](https://img.shields.io/badge/galaxy-voipnorm.roomos-blueviolet)](https://galaxy.ansible.com/ui/repo/published/voipnorm/roomos/)

Ansible collection for **Cisco RoomOS** collaboration endpoints (Room, Desk, Board series) via the xAPI.

## Features

- **`roomos_command`** — Execute xCommands (reboot, volume, dial, etc.)
- **`roomos_config`** — Set xConfigurations with full idempotency, check mode, and diff
- **`roomos_status`** — Query xStatus for conditional playbook logic

### Transport options

| Transport | Use case | Auth |
|---|---|---|
| `local` (default) | Direct HTTP to device | username + password |
| `cloud` | Webex cloud API | Webex bearer token |

## Requirements

- Python >= 3.10
- Ansible >= 2.15
- RoomOS 11.x or 26.x

**No external Python dependencies** — just install and go.

## Installation

```bash
ansible-galaxy collection install voipnorm.roomos
```

Or with a `requirements.yml`:

```yaml
collections:
  - name: voipnorm.roomos
    version: ">=0.1.0"
```

```bash
ansible-galaxy collection install -r requirements.yml
```

## Quick Start

### Local transport (direct HTTP)

```yaml
- name: Configure RoomOS devices
  hosts: roomos_devices
  connection: local
  gather_facts: false

  tasks:
    - name: Set NTP and timezone
      voipnorm.roomos.roomos_config:
        config:
          NetworkServices.NTP.Server1.Address: "10.1.1.1"
          Time.Zone: "America/Los_Angeles"
```

> With proper inventory (`roomos_username`, `roomos_password`, `ansible_host` set as host/group vars), playbooks are this clean — no auth params on every task.

### Cloud transport (Webex API)

```yaml
- name: Query device status via cloud
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Get device info
      voipnorm.roomos.roomos_status:
        paths:
          - SystemUnit.Software.Version
          - Standby.State
        transport: cloud
        device_id: "{{ device_id }}"
        token: "{{ lookup('env', 'WEBEX_TOKEN') }}"
      register: status
```

## Security

- **`validate_certs`** defaults to `false` because most RoomOS devices use self-signed certificates. Set to `true` in environments with proper CA-signed certs.
- **Credentials**: Always use Ansible Vault or environment variables. Never hardcode tokens or passwords.
- **Diff output**: Sensitive config paths (passwords, keys, SIP auth) are automatically redacted.

## Supported Devices

| Device series | RoomOS 11.x | RoomOS 26.x | CE 9.x |
|---|---|---|---|
| Room series | ✅ | ✅ | ❌ |
| Desk series | ✅ | ✅ | ❌ |
| Board series | ✅ | ✅ | ❌ |

## Documentation

- [Quick Start Guide](docs/quickstart.md)
- [Compatibility Matrix](docs/compatibility-matrix.md)
- [Development Guide](docs/development.md)
- [Architecture Decision Records](docs/adr/)

## AnsibleBlocks Integration

This collection ships with an [AnsibleBlocks](https://github.com/voipnorm/AnsibleBlocks) pack for visual playbook building. The RoomOS blocks appear automatically when the pack is installed.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and PR guidelines.

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).
