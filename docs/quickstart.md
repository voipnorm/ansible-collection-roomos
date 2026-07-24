# Quick Start Guide

## Prerequisites

- Python >= 3.10
- Ansible >= 2.15 (`pip install ansible-core`)
- A Cisco RoomOS device (Room Kit, Desk Pro, Board, etc.) running RoomOS 11.x or 26.x

## Install the collection

```bash
ansible-galaxy collection install voipnorm.roomos
```

## Option A: Local transport (direct HTTP)

### 1. Create an inventory file

```yaml
# inventory.yml
all:
  hosts:
    my-room-kit:
      ansible_host: 10.0.1.50
      roomos_username: admin
      roomos_password: "{{ vault_roomos_password }}"
      roomos_transport: local
```

### 2. Write a playbook

```yaml
# playbook.yml
---
- name: Configure RoomOS device
  hosts: my-room-kit
  connection: local
  gather_facts: false

  tasks:
    - name: Set NTP server
      voipnorm.roomos.roomos_config:
        config:
          NetworkServices.NTP.Server1.Address: "10.1.1.1"
          Time.Zone: "America/Los_Angeles"
```

### 3. Run it

```bash
ansible-playbook -i inventory.yml playbook.yml --ask-vault-pass
```

## Option B: Cloud transport (Webex API)

### 1. Get a Webex API token

Visit [developer.webex.com](https://developer.webex.com) and generate a token with these scopes:
- `spark:xapi_commands`
- `spark:xapi_statuses`
- `spark-admin:devices_read`
- `spark-admin:devices_write`

### 2. Write a playbook

```yaml
# cloud-playbook.yml
---
- name: Query device via Webex cloud
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Get device status
      voipnorm.roomos.roomos_status:
        paths:
          - SystemUnit.Software.Version
          - Standby.State
        transport: cloud
        device_id: "YOUR_DEVICE_ID"
        token: "{{ lookup('env', 'WEBEX_TOKEN') }}"
      register: status

    - name: Show result
      ansible.builtin.debug:
        var: status.values
```

### 3. Run it

```bash
export WEBEX_TOKEN="your-token-here"
ansible-playbook cloud-playbook.yml
```

## Next steps

- See the [full module documentation](https://galaxy.ansible.com/ui/repo/published/voipnorm/roomos/)
- Check the [compatibility matrix](compatibility-matrix.md) for supported devices
- Try check mode: `ansible-playbook playbook.yml --check --diff`
