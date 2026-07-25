# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Webex Cloud xAPI transport for voipnorm.roomos modules.

Validated endpoints (Gate 0.5, ADR 0004):
  - Status:  GET  /v1/xapi/status?deviceId={id}&name={path}
  - Command: POST /v1/xapi/command/{commandKey}
  - Config:  GET  /v1/deviceConfigurations?deviceId={id}&key={key}
  - Config:  PATCH /v1/deviceConfigurations?deviceId={id}
             (Content-Type: application/json-patch+json, JSON Patch body)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import time
from urllib.error import HTTPError, URLError

from ansible.module_utils.urls import open_url

from ansible_collections.voipnorm.roomos.plugins.module_utils.roomos_common import RoomOSTransport


class CloudTransport(RoomOSTransport):
    """Transport using Webex REST API (webexapis.com/v1/xapi/*)."""

    BASE_URL = 'https://webexapis.com/v1'
    MAX_RETRIES = 3
    RETRY_CODES = (429, 500, 502, 503, 504)

    def __init__(self, module):
        self.module = module
        self.device_id = module.params['device_id']
        self.token = module.params['token']
        self.validate_certs = module.params['validate_certs']
        self.timeout = module.params['timeout']

    # -----------------------------------------------------------------------
    # HTTP helper
    # -----------------------------------------------------------------------

    def _request(self, method, url, data=None, content_type='application/json'):
        """Make an HTTP request to the Webex API with retry on 429/5xx.

        Returns parsed JSON response body (dict).
        Raises Exception with user-friendly message on failure.
        """
        headers = {
            'Authorization': 'Bearer %s' % self.token,
            'Content-Type': content_type,
        }

        last_exc = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = open_url(
                    url,
                    method=method,
                    data=data,
                    headers=headers,
                    validate_certs=self.validate_certs,
                    timeout=self.timeout,
                )
                body = resp.read()
                return json.loads(body) if body else {}
            except HTTPError as e:
                if e.code in self.RETRY_CODES and attempt < self.MAX_RETRIES:
                    wait = 2 ** attempt
                    if e.code == 429:
                        retry_after = e.headers.get('Retry-After')
                        if retry_after:
                            try:
                                wait = int(retry_after)
                            except ValueError:
                                pass
                    time.sleep(wait)
                    last_exc = e
                    continue
                # Parse error body for better messages
                msg = str(e)
                try:
                    err_body = json.loads(e.read().decode('utf-8'))
                    msg = err_body.get('message', msg)
                except Exception:
                    pass
                raise Exception("Webex API error (HTTP %d): %s" % (e.code, msg))
            except URLError as e:
                raise Exception("Cannot connect to Webex API: %s" % str(e.reason))

        raise last_exc or Exception("Request failed after %d retries" % self.MAX_RETRIES)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _flatten_dict(nested, result, prefix=''):
        """Flatten nested dict to dot-notation keys.

        {'SystemUnit': {'Uptime': 61269}} → {'SystemUnit.Uptime': 61269}
        """
        for key, value in nested.items():
            full_key = '%s.%s' % (prefix, key) if prefix else key
            if isinstance(value, dict):
                CloudTransport._flatten_dict(value, result, full_key)
            else:
                result[full_key] = value

    # -----------------------------------------------------------------------
    # Transport interface
    # -----------------------------------------------------------------------

    def execute_command(self, command_name, arguments=None):
        # type: (str, dict | None) -> dict
        """POST /v1/xapi/command/{commandKey}"""
        url = '%s/xapi/command/%s' % (self.BASE_URL, command_name)
        body = json.dumps({
            'deviceId': self.device_id,
            'arguments': arguments or {},
        })
        data = self._request('POST', url, data=body)
        return data.get('result', {})

    def get_configuration(self, paths):
        # type: (list[str]) -> dict
        """GET /v1/deviceConfigurations?deviceId={id}&key={key}

        Returns dict of path → effective value (uses appliedConfigurationValue).
        """
        result = {}
        for path in paths:
            url = '%s/deviceConfigurations?deviceId=%s&key=%s' % (
                self.BASE_URL, self.device_id, path)
            data = self._request('GET', url)
            items = data.get('items', {})
            for key, info in items.items():
                # Use appliedConfigurationValue for the effective value (ADR 0004 §4)
                applied = info.get('appliedConfigurationValue')
                if applied and applied.get('value') is not None:
                    result[key] = applied['value']
                else:
                    result[key] = info.get('value')
        return result

    def set_configuration(self, config):
        # type: (dict) -> dict
        """PATCH /v1/deviceConfigurations?deviceId={id}

        Uses JSON Patch format (RFC 6902) with application/json-patch+json.
        """
        url = '%s/deviceConfigurations?deviceId=%s' % (self.BASE_URL, self.device_id)
        patch_ops = []
        for path, value in config.items():
            patch_ops.append({
                'op': 'replace',
                'path': '%s/sources/configured/value' % path,
                'value': value,
            })
        body = json.dumps(patch_ops)
        self._request('PATCH', url, data=body,
                      content_type='application/json-patch+json')
        return {'success': True}

    def get_status(self, paths):
        # type: (list[str]) -> dict
        """GET /v1/xapi/status?deviceId={id}&name={path}

        One request per path. Invalid paths return empty result (HTTP 200),
        not an error (ADR 0004 §2).
        """
        result = {}
        for path in paths:
            url = '%s/xapi/status?deviceId=%s&name=%s' % (
                self.BASE_URL, self.device_id, path)
            data = self._request('GET', url)
            nested = data.get('result', {})
            if nested:
                self._flatten_dict(nested, result)
        return result
