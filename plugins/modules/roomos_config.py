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
  - Configuration values are protected from logging; matching ordinary diff values may also be masked.
  - Paths are read before mutation and changed paths are written individually.
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
    validate_certs: true

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
  description: List of config paths that failed to read or apply.
  returned: always
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
    REDACTED_VALUE,
    get_transport,
    is_sensitive_path,
    config_values_equal,
    validate_path,
)


def main():
    argument_spec = dict(
        config=dict(type='dict', required=True, no_log=True),
        failure_mode=dict(type='str', choices=['fail', 'warn', 'ignore'], default='fail'),
    )
    argument_spec.update(ROOMOS_COMMON_ARGS)

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    desired_config = module.params['config']
    failure_mode = module.params['failure_mode']

    # Validate before any requests, including check mode.
    try:
        for path, value in desired_config.items():
            validate_path(path)
            if value is None or isinstance(value, (dict, list)):
                raise ValueError('Configuration values must be scalars')
        transport = get_transport(module)
    except Exception:
        module.fail_json(msg='Invalid configuration or connection parameters')

    current_values = {}
    failed_keys = []
    for path in desired_config:
        try:
            values = transport.get_configuration([path])
            if path not in values:
                raise ValueError('Configuration path is unavailable')
            current_values[path] = values[path]
            if is_sensitive_path(path) and values[path] is not None:
                module.no_log_values.add(str(values[path]))
        except Exception:
            failed_keys.append(path)
            if failure_mode == 'warn':
                module.warn('Could not read configuration path: %s' % path)
    if failed_keys and failure_mode == 'fail':
        module.fail_json(msg='Could not read requested configuration paths',
                         changed=False, changed_keys=[], failed_keys=failed_keys)

    # Compare with normalization
    changed_keys = []
    for path, desired_value in desired_config.items():
        if path in failed_keys:
            continue
        current = current_values[path]
        try:
            desired_value = transport.prepare_configuration_value(path, desired_value)
        except (ValueError, TypeError, OverflowError):
            module.fail_json(msg='Invalid configuration value for path: %s' % path)
        if not config_values_equal(desired_value, current, path):
            changed_keys.append(path)

    if not changed_keys:
        module.exit_json(changed=False, changed_keys=[], failed_keys=failed_keys)

    # Build diff (redact sensitive paths)
    diff = None
    if module._diff:
        before = {}
        after = {}
        for k in changed_keys:
            if is_sensitive_path(k):
                before[k] = REDACTED_VALUE
                after[k] = REDACTED_VALUE
            else:
                before[k] = current_values.get(k, '')
                after[k] = desired_config[k]
        diff = {'before': before, 'after': after}

    if module.check_mode:
        module.exit_json(changed=True, changed_keys=changed_keys, failed_keys=failed_keys, diff=diff)

    # Apply changes
    applied_keys = []
    for path in changed_keys:
        try:
            transport.set_configuration({path: desired_config[path]})
            applied_keys.append(path)
        except Exception:
            failed_keys.append(path)
            if failure_mode == 'fail':
                module.fail_json(msg='Failed to apply configuration path: %s' % path,
                                 changed=bool(applied_keys), changed_keys=applied_keys,
                                 failed_keys=failed_keys)
            if failure_mode == 'warn':
                module.warn('Failed to apply configuration path: %s' % path)
    if diff:
        diff = {side: {key: value for key, value in data.items() if key in applied_keys}
                for side, data in diff.items()}

    module.exit_json(
        changed=bool(applied_keys),
        changed_keys=applied_keys,
        failed_keys=failed_keys,
        diff=diff,
    )


if __name__ == '__main__':
    main()
