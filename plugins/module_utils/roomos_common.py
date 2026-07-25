# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared argument specs and transport factory for voipnorm.roomos modules."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from abc import ABC, abstractmethod

from ansible.module_utils.basic import env_fallback


# ---------------------------------------------------------------------------
# Transport interface
# ---------------------------------------------------------------------------

class RoomOSTransport(ABC):
    """Abstract base class for RoomOS transport implementations."""

    @abstractmethod
    def execute_command(self, command_name, arguments=None):
        # type: (str, dict | None) -> dict
        """Execute an xCommand and return the response."""

    @abstractmethod
    def get_configuration(self, paths):
        # type: (list[str]) -> dict
        """Read one or more xConfiguration paths."""

    @abstractmethod
    def set_configuration(self, config):
        # type: (dict) -> dict
        """Write xConfiguration key/value pairs."""

    @abstractmethod
    def get_status(self, paths):
        # type: (list[str]) -> dict
        """Read one or more xStatus paths."""


# ---------------------------------------------------------------------------
# Common module arguments
# ---------------------------------------------------------------------------

ROOMOS_COMMON_ARGS = dict(
    transport=dict(
        type='str',
        choices=['cloud', 'local'],
        default='local',
        fallback=(env_fallback, ['ROOMOS_TRANSPORT']),
    ),
    # Cloud-only
    device_id=dict(
        type='str',
        fallback=(env_fallback, ['ROOMOS_DEVICE_ID']),
    ),
    token=dict(
        type='str',
        no_log=True,
        fallback=(env_fallback, ['ROOMOS_TOKEN']),
    ),
    # Local-only
    host=dict(
        type='str',
        fallback=(env_fallback, ['ROOMOS_HOST']),
    ),
    username=dict(
        type='str',
        fallback=(env_fallback, ['ROOMOS_USERNAME']),
    ),
    password=dict(
        type='str',
        no_log=True,
        fallback=(env_fallback, ['ROOMOS_PASSWORD']),
    ),
    # Shared
    validate_certs=dict(type='bool', default=False),
    timeout=dict(type='int', default=30),
)


# ---------------------------------------------------------------------------
# Sensitive config path patterns (redacted in diff output)
# ---------------------------------------------------------------------------

SENSITIVE_PATH_PATTERNS = [
    '*.Password',
    '*.Passphrase',
    '*.Secret',
    '*.Token',
    '*.Key',
    '*.PIN',
    'SIP.Authentication.*',
    'Provisioning.ExternalManager.*',
    'NetworkServices.SNMP.CommunityName',
    'Security.Session.*',
]


def is_sensitive_path(path):
    # type: (str) -> bool
    """Check if a config path matches a sensitive pattern.

    Uses fnmatch-style glob matching against SENSITIVE_PATH_PATTERNS.
    """
    from fnmatch import fnmatch
    return any(fnmatch(path, pattern) for pattern in SENSITIVE_PATH_PATTERNS)


REDACTED_VALUE = '********'


# ---------------------------------------------------------------------------
# Value normalization for idempotency
# ---------------------------------------------------------------------------

def normalize_config_value(value, path=''):
    # type: (str, str) -> str
    """Normalize a config value for comparison.

    Handles bool, int, and enum normalization so that values like
    "True"/"true"/"on"/"1" all compare as equal.
    """
    value = str(value).strip()

    # Boolean normalization
    if value.lower() in ('true', 'on', 'yes', '1'):
        return 'True'
    if value.lower() in ('false', 'off', 'no', '0'):
        return 'False'

    # Integer normalization
    try:
        return str(int(value))
    except ValueError:
        pass

    return value


# ---------------------------------------------------------------------------
# Transport factory
# ---------------------------------------------------------------------------

def get_transport(module):
    """Instantiate the correct transport based on module params.

    Also resolves inventory variable fallbacks for host/username/password.
    """
    transport = module.params['transport']

    if transport == 'cloud':
        # Validate cloud-required args
        for arg in ('device_id', 'token'):
            if not module.params.get(arg):
                module.fail_json(msg="transport=cloud requires '%s'" % arg)

        from ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud import CloudTransport
        return CloudTransport(module)

    else:
        # Validate local-required args
        host = module.params.get('host')
        if not host:
            module.fail_json(
                msg="transport=local requires 'host'. Set it directly, "
                    "use ROOMOS_HOST env var, or use host: '{{ ansible_host }}' in your task.")

        username = module.params.get('username')
        if not username:
            module.fail_json(
                msg="transport=local requires 'username'. Set it directly "
                    "or use ROOMOS_USERNAME env var.")

        password = module.params.get('password')
        if password is None:
            module.fail_json(
                msg="transport=local requires 'password'. Set it directly "
                    "or use ROOMOS_PASSWORD env var.")

        from ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local import LocalTransport
        return LocalTransport(module, host=host, username=username, password=password)
