# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared argument specs and transport factory for voipnorm.roomos modules."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from abc import ABC, abstractmethod
import re
from urllib.parse import urlsplit

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

    def prepare_configuration_value(self, path, value):
        return value


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
    validate_certs=dict(type='bool', default=True),
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
    from fnmatch import fnmatchcase
    canonical = re.sub(r'\[([0-9]+)\]', r'.\1', path).lower()
    return (any(fnmatchcase(canonical, pattern.lower()) for pattern in SENSITIVE_PATH_PATTERNS)
            or any(word in canonical.split('.')[-1]
                   for word in ('password', 'passphrase', 'secret', 'token', 'community', 'privatekey')))


REDACTED_VALUE = '********'


# ---------------------------------------------------------------------------
# Value normalization for idempotency
# ---------------------------------------------------------------------------

def normalize_config_value(value, path=''):
    # type: (str, str) -> str
    """Return the exact textual value without guessing its device type."""
    # Strings (including passwords, enum names and leading zeroes) are exact.
    return str(value)


def config_values_equal(desired, current, path=''):
    numbers = (int, float)
    if (isinstance(desired, numbers) and isinstance(current, numbers)
            and not isinstance(desired, bool) and not isinstance(current, bool)):
        return desired == current
    return normalize_config_value(desired, path) == normalize_config_value(current, path)


def validate_path(path, command=False):
    """Accept xAPI names with dot or bracket indices, never XML/URL syntax."""
    pattern = r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*' if command else (
        r'[A-Za-z_][A-Za-z0-9_]*(?:\[[1-9][0-9]*\])?'
        r'(?:\.(?:[A-Za-z_][A-Za-z0-9_]*(?:\[[1-9][0-9]*\])?|[1-9][0-9]*))*')
    if not isinstance(path, str) or len(path) > 512 or not re.fullmatch(pattern, path):
        raise ValueError('Invalid xAPI path')
    return path


def path_segments(path):
    validate_path(path)
    return re.sub(r'\[([0-9]+)\]', r'.\1', path).split('.')


def cloud_path(path):
    """Webex configuration keys use bracket indices."""
    parts = path_segments(path)
    result = []
    for part in parts:
        if part.isdigit():
            result[-1] += '[%s]' % part
        else:
            result.append(part)
    return '.'.join(result)


def validate_host(host):
    parsed = urlsplit('https://' + host)
    if (not parsed.hostname or parsed.username is not None or parsed.password is not None
            or parsed.path or parsed.query or parsed.fragment
            or any(c.isspace() for c in host) or '\\' in host):
        raise ValueError('host must be a hostname or IP address, optionally with a port')
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError('Invalid host port')


def read_response(response):
    """Bound response memory and always release the HTTP connection."""
    try:
        body = response.read(8 * 1024 * 1024 + 1)
        if len(body) > 8 * 1024 * 1024:
            raise ValueError('API response exceeds 8 MiB')
        return body
    finally:
        response.close()


# ---------------------------------------------------------------------------
# Transport factory
# ---------------------------------------------------------------------------

def get_transport(module):
    """Instantiate the correct transport based on module params.

    Inventory fallbacks are resolved by the action plugin before execution.
    """
    transport = module.params['transport']
    if module.params['timeout'] <= 0:
        module.fail_json(msg='timeout must be positive')

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
