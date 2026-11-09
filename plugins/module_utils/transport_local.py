# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Local HTTP XML transport for voipnorm.roomos modules.

Validated endpoints (Gate 0.5, ADR 0004):
  - Status:  GET  /getxml?location=/Status/{path}
  - Config:  GET  /getxml?location=/Configuration/{path}
  - Command: POST /putxml  (XML body with command="True" attribute)
  - Config:  POST /putxml  (XML body with <Configuration> root)

Key findings from validation:
  - Commands require command="True" attribute on the action element
  - Errors return HTTP 200 with error in XML body — must parse body
  - Config write success: <Configuration><Success/></Configuration>
  - Command success: element with status="OK"
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.parse import quote

from ansible.module_utils.urls import open_url

from ansible_collections.voipnorm.roomos.plugins.module_utils.roomos_common import (
    RoomOSTransport, path_segments, read_response, validate_host, validate_path,
)


class LocalTransport(RoomOSTransport):
    """Transport using direct HTTP XML (/putxml, /getxml) to RoomOS devices."""

    MAX_RETRIES = 3
    RETRY_CODES = (429, 500, 502, 503, 504)

    def __init__(self, module, host, username, password):
        validate_host(host)
        self.module = module
        self.host = host
        self.username = username
        self.password = password
        self.validate_certs = module.params['validate_certs']
        self.timeout = module.params['timeout']
        self.base_url = 'https://%s' % host

    # -----------------------------------------------------------------------
    # HTTP helper
    # -----------------------------------------------------------------------

    def _request(self, method, path, data=None):
        """Make an HTTP request to the local device with retry on 5xx.

        Returns the response body as a string.
        Raises Exception with user-friendly message on failure.
        """
        url = '%s/%s' % (self.base_url, path)
        headers = {'Content-Type': 'text/xml'}

        last_exc = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = open_url(
                    url,
                    method=method,
                    data=data,
                    headers=headers,
                    url_username=self.username,
                    url_password=self.password,
                    force_basic_auth=True,
                    validate_certs=self.validate_certs,
                    timeout=self.timeout,
                    follow_redirects='none',
                    unredirected_headers=['Authorization'],
                    use_netrc=False,
                )
                return read_response(resp).decode('utf-8')
            except HTTPError as e:
                if method == 'GET' and e.code in self.RETRY_CODES and attempt < self.MAX_RETRIES:
                    e.close()
                    time.sleep(2 ** attempt)
                    last_exc = e
                    continue
                if e.code == 401:
                    raise Exception(
                        "Authentication failed for %s (HTTP 401). "
                        "Check username/password." % self.host)
                e.close()
                raise Exception("Device error on %s (HTTP %d)" % (self.host, e.code))
            except URLError as e:
                raise Exception("Cannot connect to %s: %s" % (
                    self.host, str(e.reason)))

        raise last_exc or Exception(
            "Request to %s failed after %d retries" % (self.host, self.MAX_RETRIES))

    # -----------------------------------------------------------------------
    # XML builders
    # -----------------------------------------------------------------------

    @staticmethod
    def _build_command_xml(command_name, arguments=None):
        """Build xCommand XML from dot-notation name and arguments dict.

        'Audio.Volume.Set', {'Level': 50} →
        <Command>
          <Audio><Volume><Set command="True"><Level>50</Level></Set></Volume></Audio>
        </Command>
        """
        validate_path(command_name, command=True)
        parts = command_name.split('.')
        root = ET.Element('Command')
        parent = root
        for i, part in enumerate(parts):
            elem = ET.SubElement(parent, part)
            if i == len(parts) - 1:
                # Last segment is the action — mark with command="True" (ADR 0004 §6)
                elem.set('command', 'True')
                if arguments:
                    for key, value in arguments.items():
                        validate_path(key, command=True)
                        if '.' in key:
                            raise ValueError('Command argument names must be single identifiers')
                        arg_elem = ET.SubElement(elem, key)
                        arg_elem.text = str(value)
            parent = elem
        return ET.tostring(root, encoding='unicode')

    @staticmethod
    def _build_config_xml(config):
        """Build xConfiguration XML from path/value dict.

        {'Audio.DefaultVolume': '50', 'Time.Zone': 'US/Pacific'} →
        <Configuration>
          <Audio><DefaultVolume>50</DefaultVolume></Audio>
          <Time><Zone>US/Pacific</Zone></Time>
        </Configuration>
        """
        root = ET.Element('Configuration')
        for path, value in config.items():
            parts = path_segments(path)
            parent = root
            for i, part in enumerate(parts):
                if part.isdigit():
                    continue
                item = parts[i + 1] if i + 1 < len(parts) and parts[i + 1].isdigit() else None
                existing = next((child for child in parent
                                 if child.tag == part and child.get('item') == item), None)
                if existing is None:
                    existing = ET.SubElement(parent, part, {'item': item} if item else {})
                parent = existing
            parent.text = str(value)
        return ET.tostring(root, encoding='unicode')

    # -----------------------------------------------------------------------
    # XML parsers
    # -----------------------------------------------------------------------

    @staticmethod
    def _extract_leaf_values(xml_string):
        """Parse XML response and extract leaf text values as flat dict.

        Skips the root element (Configuration/Status) and builds
        dot-notation paths from the nested structure.

        Handles item="N" attributes for indexed elements:
          <USBC item="1"><Connected>False</Connected></USBC>
          → {'USBC.1.Connected': 'False'}
        """
        root = LocalTransport._parse_xml(xml_string)
        if root.tag not in ('Configuration', 'Status'):
            raise ValueError('Unexpected xAPI response root')
        result = {}
        for child in root:
            tag = child.tag
            item = child.get('item')
            start_path = [tag, item] if item else [tag]
            LocalTransport._walk_xml(child, start_path, result)
        return result

    @staticmethod
    def _walk_xml(element, path_parts, result):
        """Recursively walk XML and collect leaf text values."""
        children = list(element)
        if not children:
            result['.'.join(path_parts)] = element.text if element.text is not None else ''
        else:
            for child in children:
                tag = child.tag
                item = child.get('item')
                child_path = path_parts + ([tag, item] if item else [tag])
                LocalTransport._walk_xml(child, child_path, result)

    @staticmethod
    def _check_command_response(xml_string, command_name):
        """Verify command response indicates success (ADR 0004 §7+8).

        Local xAPI returns HTTP 200 even on errors — must parse XML body.
        Success: element with status="OK".
        Error: <ActionError><Reason>...</Reason></ActionError> or status="Error".
        """
        root = LocalTransport._parse_xml(xml_string)
        if root.tag != 'Command':
            raise ValueError('Unexpected command response root')

        # Check for ActionError (e.g. "No action detected in document")
        error_elem = root.find('.//ActionError')
        if error_elem is not None:
            raise Exception("xCommand '%s' failed: ActionError" % command_name)

        # Check for elements with status="Error"
        for elem in root.iter():
            status = elem.get('status')
            if status and status.lower() == 'error':
                raise Exception("xCommand '%s' failed: error status" % command_name)

        # Collect result elements (those with status attributes or text)
        result = {}
        for elem in root.iter():
            status = elem.get('status')
            if status:
                result[elem.tag] = {'status': status}
                values = {}
                for child in elem:
                    LocalTransport._walk_xml(child, [child.tag], values)
                result[elem.tag].update(values)
        if not any(elem.get('status', '').lower() == 'ok' for elem in root.iter()):
            raise ValueError('Command response does not confirm success')
        return result

    @staticmethod
    def _check_config_response(xml_string):
        """Verify config write response indicates success (ADR 0004 §7).

        Success: <Configuration><Success/></Configuration>
        """
        root = LocalTransport._parse_xml(xml_string)
        if root.tag != 'Configuration':
            raise ValueError('Unexpected configuration response root')
        if any(elem.get('status', '').lower() == 'error' for elem in root.iter()):
            raise ValueError('Configuration write returned error status')

        # Check for explicit error elements
        failure = root.find('.//Failure')
        if failure is None:
            failure = root.find('.//Error')
        if failure is not None:
            raise Exception('Configuration write failed: device rejected request')
        if root.find('.//Success') is None:
            raise ValueError('Configuration response does not confirm success')
        return True

    @staticmethod
    def _parse_xml(xml_string):
        if '<!DOCTYPE' in xml_string.upper() or '<!ENTITY' in xml_string.upper():
            raise ValueError('DTD and entity declarations are not allowed')
        root = ET.fromstring(xml_string)
        pending = [(root, 0)]
        while pending:
            node, depth = pending.pop()
            if depth > 64:
                raise ValueError('XML response is too deeply nested')
            pending.extend((child, depth + 1) for child in node)
        return root

    @staticmethod
    def _query_path(path):
        parts = path_segments(path)
        result = []
        for part in parts:
            if part.isdigit():
                result[-1] += "[@item='%s']" % part
            else:
                result.append(part)
        return quote('/'.join(result), safe='/')

    # -----------------------------------------------------------------------
    # Transport interface
    # -----------------------------------------------------------------------

    def execute_command(self, command_name, arguments=None):
        # type: (str, dict | None) -> dict
        """POST /putxml with xCommand XML."""
        xml_body = self._build_command_xml(command_name, arguments)
        resp_body = self._request('POST', 'putxml', data=xml_body)
        return self._check_command_response(resp_body, command_name)

    def get_configuration(self, paths):
        # type: (list[str]) -> dict
        """GET /getxml?location=/Configuration/{path} for each path."""
        result = {}
        for path in paths:
            url_segment = self._query_path(path)
            url_path = 'getxml?location=/Configuration/%s' % url_segment
            resp_body = self._request('GET', url_path)
            values = self._extract_leaf_values(resp_body)
            canonical = '.'.join(path_segments(path))
            if canonical in values:
                result[path] = values[canonical]
        return result

    def set_configuration(self, config):
        # type: (dict) -> dict
        """POST /putxml with xConfiguration XML."""
        xml_body = self._build_config_xml(config)
        resp_body = self._request('POST', 'putxml', data=xml_body)
        self._check_config_response(resp_body)
        return {'success': True}

    def get_status(self, paths):
        # type: (list[str]) -> dict
        """GET /getxml?location=/Status/{path} for each path."""
        result = {}
        for path in paths:
            url_segment = self._query_path(path)
            url_path = 'getxml?location=/Status/%s' % url_segment
            resp_body = self._request('GET', url_path)
            values = self._extract_leaf_values(resp_body)
            canonical = '.'.join(path_segments(path))
            if canonical in values:
                result[path] = values[canonical]
            else:
                result.update(values)
        return result
