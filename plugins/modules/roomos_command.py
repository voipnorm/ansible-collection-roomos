#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Execute xCommands on Cisco RoomOS devices."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: roomos_command
short_description: Execute xCommands on Cisco RoomOS devices
version_added: "0.1.0"
description:
  - Execute arbitrary xCommands on Cisco RoomOS collaboration endpoints.
  - Supports both local HTTP and Webex cloud transports.
  - Commands are actions and always report C(changed=true).
  - In check mode, reports what would execute without making API calls.
options:
  command:
    description:
      - The xCommand path to execute.
      - Use dot notation, e.g. C(SystemUnit.Boot) or C(Audio.Volume.Set).
    type: str
    required: true
  arguments:
    description:
      - Dictionary of arguments to pass to the xCommand.
    type: dict
    default: {}
extends_documentation_fragment:
  - voipnorm.roomos.roomos
author:
  - Chris Norman (@voipnorm)
'''

EXAMPLES = r'''
- name: Reboot the device
  voipnorm.roomos.roomos_command:
    command: SystemUnit.Boot
    arguments:
      Action: Restart
    transport: local
    host: "{{ ansible_host }}"
    username: admin
    password: "{{ device_password }}"

- name: Set volume via cloud API
  voipnorm.roomos.roomos_command:
    command: Audio.Volume.Set
    arguments:
      Level: "50"
    transport: cloud
    device_id: "{{ device_id }}"
    token: "{{ webex_token }}"
'''

RETURN = r'''
output:
  description: The raw response from the xCommand execution.
  returned: success
  type: dict
  sample: {"CommandResponse": {"BootResult": {"status": "OK"}}}
would_execute:
  description: Set to true in check mode to indicate the command would have been executed.
  returned: check mode
  type: bool
  sample: true
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.voipnorm.roomos.plugins.module_utils.roomos_common import (
    ROOMOS_COMMON_ARGS,
    get_transport,
)


def main():
    argument_spec = dict(
        command=dict(type='str', required=True),
        arguments=dict(type='dict', default={}),
    )
    argument_spec.update(ROOMOS_COMMON_ARGS)

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    command = module.params['command']
    arguments = module.params['arguments']

    if module.check_mode:
        module.exit_json(
            changed=True,
            would_execute=True,
            msg="Would execute xCommand: %s" % command,
        )

    transport = get_transport(module)

    try:
        result = transport.execute_command(command, arguments)
    except Exception as e:
        module.fail_json(msg="xCommand '%s' failed: %s" % (command, str(e)))

    module.exit_json(
        changed=True,
        output=result,
    )


if __name__ == '__main__':
    main()
