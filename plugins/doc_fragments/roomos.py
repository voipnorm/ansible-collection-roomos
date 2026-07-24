# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Documentation fragment for voipnorm.roomos modules."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):

    DOCUMENTATION = r'''
options:
  transport:
    description:
      - Transport method to communicate with the device.
      - C(local) uses direct HTTP XML calls (putxml/getxml).
      - C(cloud) uses the Webex REST API.
    type: str
    choices: ['cloud', 'local']
    default: local
  device_id:
    description:
      - Webex device ID. Required when C(transport=cloud).
      - Falls back to C(roomos_device_id) inventory variable or C(ROOMOS_DEVICE_ID) environment variable.
    type: str
  token:
    description:
      - Webex API bearer token. Required when C(transport=cloud).
      - Falls back to C(roomos_token) inventory variable or C(ROOMOS_TOKEN) environment variable.
      - Use C(lookup('env', 'WEBEX_TOKEN')) or Ansible Vault — never hardcode tokens.
    type: str
  host:
    description:
      - Device IP address or hostname. Required when C(transport=local).
      - Falls back to C(ansible_host) inventory variable.
    type: str
  username:
    description:
      - HTTP Basic auth username. Required when C(transport=local).
      - Falls back to C(roomos_username) inventory variable or C(ROOMOS_USERNAME) environment variable.
    type: str
  password:
    description:
      - HTTP Basic auth password. Required when C(transport=local).
      - Falls back to C(roomos_password) inventory variable or C(ROOMOS_PASSWORD) environment variable.
      - Use Ansible Vault or environment variables — never hardcode passwords.
    type: str
  validate_certs:
    description:
      - Whether to validate TLS certificates.
      - Most RoomOS devices use self-signed certificates, so this defaults to C(false).
      - Set to C(true) in production environments with proper CA-signed certificates.
    type: bool
    default: false
  timeout:
    description:
      - HTTP request timeout in seconds.
    type: int
    default: 30
notes:
  - This collection requires Python >= 3.10 and Ansible >= 2.15.
  - Only RoomOS 11.x and 26.x are supported. CE 9.x is out of scope.
  - Modules resolve auth parameters via a fallback chain —
    explicit param > C(roomos_*) inventory var > standard Ansible var > environment var.
  - For local transport, C(validate_certs=false) is the default because most RoomOS devices
    use self-signed certificates. Review the security implications for your environment.
requirements:
  - No external Python dependencies — uses only C(ansible.module_utils.urls).
'''
