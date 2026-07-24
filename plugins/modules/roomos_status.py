#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Query xStatus values from Cisco RoomOS devices."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: roomos_status
short_description: Query xStatus values from Cisco RoomOS devices
version_added: "0.1.0"
description:
  - Query one or more xStatus paths from Cisco RoomOS endpoints.
  - Read-only — always reports C(changed=false).
  - Useful for conditional logic in playbooks.
options:
  paths:
    description:
      - List of xStatus paths to query.
      - Use dot notation, e.g. C(Standby.State) or C(SystemUnit.Uptime).
    type: list
    elements: str
    required: true
  on_missing:
    description:
      - How to handle status paths that don't exist on the device.
      - C(warn) returns null and emits a warning.
      - C(fail) causes the module to fail.
      - C(ignore) silently returns null.
    type: str
    choices: ['warn', 'fail', 'ignore']
    default: warn
extends_documentation_fragment:
  - voipnorm.roomos.roomos
author:
  - Chris Norman (@voipnorm)
'''

EXAMPLES = r'''
- name: Get device status
  voipnorm.roomos.roomos_status:
    paths:
      - Standby.State
      - SystemUnit.Uptime
      - Network.1.IPv4.Address
    transport: cloud
    device_id: "{{ device_id }}"
    token: "{{ webex_token }}"
  register: device_status

- name: Wake device if in standby
  voipnorm.roomos.roomos_command:
    command: Standby.Deactivate
    transport: cloud
    device_id: "{{ device_id }}"
    token: "{{ webex_token }}"
  when: device_status.values['Standby.State'] == 'Standby'
'''

RETURN = r'''
values:
  description: Dictionary mapping each queried path to its current value.
  returned: success
  type: dict
  sample: {"Standby.State": "Off", "SystemUnit.Uptime": "3600"}
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.voipnorm.roomos.plugins.module_utils.roomos_common import (
    ROOMOS_COMMON_ARGS,
    get_transport,
)


def main():
    argument_spec = dict(
        paths=dict(type='list', elements='str', required=True),
        on_missing=dict(type='str', choices=['warn', 'fail', 'ignore'], default='warn'),
    )
    argument_spec.update(ROOMOS_COMMON_ARGS)

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    paths = module.params['paths']
    on_missing = module.params['on_missing']

    transport = get_transport(module)

    try:
        raw_values = transport.get_status(paths)
    except Exception as e:
        module.fail_json(msg="Failed to query status: %s" % str(e))

    # Handle missing paths
    values = {}
    for path in paths:
        if path in raw_values:
            values[path] = raw_values[path]
        else:
            if on_missing == 'fail':
                module.fail_json(msg="Status path not found: %s" % path)
            elif on_missing == 'warn':
                module.warn("Status path not found: %s" % path)
            values[path] = None

    module.exit_json(changed=False, values=values)


if __name__ == '__main__':
    main()
