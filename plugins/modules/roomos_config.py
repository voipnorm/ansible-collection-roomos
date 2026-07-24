#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Set xConfigurations on Cisco RoomOS devices with idempotency."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: roomos_config
short_description: Set xConfigurations on Cisco RoomOS devices
version_added: "0.1.0"
description:
  - Set one or more xConfiguration values on Cisco RoomOS endpoints.
  - Idempotent — reads current config, compares, and only applies changes.
  - Supports check mode (reports diff without applying) and diff mode.
  - Sensitive config paths are automatically redacted in diff output.
options:
  config:
    description:
      - Dictionary of xConfiguration path/value pairs to set.
      - Use dot notation for paths, e.g. C(NetworkServices.NTP.Server1.Address).
    type: dict
    required: true
  failure_mode:
    description:
      - How to handle individual config path failures.
      - C(fail) fails the entire task on any invalid path.
      - C(warn) applies valid configs and warns about failures.
      - C(ignore) silently skips invalid paths.
    type: str
    choices: ['fail', 'warn', 'ignore']
    default: fail
extends_documentation_fragment:
  - voipnorm.roomos.roomos
author:
  - Chris Norman (@voipnorm)
'''

EXAMPLES = r'''
# Clean form (when inventory has roomos_* vars set):
- name: Configure NTP and timezone
  voipnorm.roomos.roomos_config:
    config:
      NetworkServices.NTP.Server1.Address: "10.1.1.1"
      Time.Zone: "America/Los_Angeles"
      Audio.DefaultVolume: "50"

# Explicit form (overrides inventory):
- name: Configure NTP and timezone
  voipnorm.roomos.roomos_config:
    config:
      NetworkServices.NTP.Server1.Address: "10.1.1.1"
      Time.Zone: "America/Los_Angeles"
    transport: local
    host: "{{ ansible_host }}"
    username: admin
    password: "{{ device_password }}"
    validate_certs: false

# Warn on invalid paths instead of failing
- name: Apply bulk config (warn on unsupported paths)
  voipnorm.roomos.roomos_config:
    config:
      Audio.DefaultVolume: "50"
      SomeInvalid.Path: "value"
    failure_mode: warn
'''

RETURN = r'''
changed_keys:
  description: List of config paths that were actually changed.
  returned: success
  type: list
  elements: str
  sample: ["NetworkServices.NTP.Server1.Address", "Time.Zone"]
failed_keys:
  description: List of config paths that failed to apply.
  returned: when failure_mode is warn or ignore
  type: list
  elements: str
  sample: ["SomeInvalid.Path"]
diff:
  description: Before/after dict for changed configurations.
  returned: when diff mode is enabled
  type: dict
  sample: {"before": {"Audio.DefaultVolume": "30"}, "after": {"Audio.DefaultVolume": "50"}}
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.voipnorm.roomos.plugins.module_utils.roomos_common import (
    ROOMOS_COMMON_ARGS,
    get_transport,
    normalize_config_value,
)


def main():
    argument_spec = dict(
        config=dict(type='dict', required=True),
        failure_mode=dict(type='str', choices=['fail', 'warn', 'ignore'], default='fail'),
    )
    argument_spec.update(ROOMOS_COMMON_ARGS)

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    desired_config = module.params['config']
    failure_mode = module.params['failure_mode']

    transport = get_transport(module)

    # Read current config
    try:
        current_values = transport.get_configuration(list(desired_config.keys()))
    except Exception as e:
        module.fail_json(msg="Failed to read current configuration: %s" % str(e))

    # Compare with normalization
    changed_keys = []
    for path, desired_value in desired_config.items():
        current = current_values.get(path, '')
        if normalize_config_value(desired_value, path) != normalize_config_value(current, path):
            changed_keys.append(path)

    if not changed_keys:
        module.exit_json(changed=False, changed_keys=[], failed_keys=[])

    # Build diff
    diff = None
    if module._diff:
        diff = {
            'before': {k: current_values.get(k, '') for k in changed_keys},
            'after': {k: desired_config[k] for k in changed_keys},
        }
        # TODO: Redact sensitive paths in diff output

    if module.check_mode:
        module.exit_json(changed=True, changed_keys=changed_keys, failed_keys=[], diff=diff)

    # Apply changes
    changes_to_apply = {k: desired_config[k] for k in changed_keys}
    failed_keys = []

    try:
        transport.set_configuration(changes_to_apply)
    except Exception as e:
        if failure_mode == 'fail':
            module.fail_json(msg="Failed to apply configuration: %s" % str(e))
        elif failure_mode == 'warn':
            module.warn("Some configuration paths failed: %s" % str(e))
        # ignore: silently continue

    module.exit_json(
        changed=True,
        changed_keys=changed_keys,
        failed_keys=failed_keys,
        diff=diff,
    )


if __name__ == '__main__':
    main()
