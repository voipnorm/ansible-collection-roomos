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

from ansible.module_utils.urls import open_url

from ansible_collections.voipnorm.roomos.plugins.module_utils.roomos_common import RoomOSTransport


class LocalTransport(RoomOSTransport):
    """Transport using direct HTTP XML (/putxml, /getxml) to RoomOS devices."""

    MAX_RETRIES = 3
    RETRY_CODES = (429, 500, 502, 503, 504)

    def __init__(self, module, host, username, password):
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
                )
                return resp.read().decode('utf-8')
            except HTTPError as e:
                if e.code in self.RETRY_CODES and attempt < self.MAX_RETRIES:
                    time.sleep(2 ** attempt)
                    last_exc = e
                    continue
                if e.code == 401:
                    raise Exception(
                        "Authentication failed for %s (HTTP 401). "
                        "Check username/password." % self.host)
                raise Exception("Device error on %s (HTTP %d): %s" % (
                    self.host, e.code, str(e)))
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
            parts = path.split('.')
            parent = root
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    elem = ET.SubElement(parent, part)
                    elem.text = str(value)
                else:
                    existing = parent.find(part)
                    if existing is not None:
                        parent = existing
                    else:
                        parent = ET.SubElement(parent, part)
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
        root = ET.fromstring(xml_string)
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
            if element.text and element.text.strip():
                result['.'.join(path_parts)] = element.text.strip()
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
        root = ET.fromstring(xml_string)

        # Check for ActionError (e.g. "No action detected in document")
        error_elem = root.find('.//ActionError')
        if error_elem is not None:
            reason = root.find('.//Reason')
            msg = reason.text.strip() if reason is not None and reason.text else 'Unknown error'
            raise Exception("xCommand '%s' failed: %s" % (command_name, msg))

        # Check for elements with status="Error"
        for elem in root.iter():
            status = elem.get('status')
            if status and status.lower() == 'error':
                reason = elem.find('Reason')
                msg = reason.text.strip() if reason is not None and reason.text else 'Unknown error'
                raise Exception("xCommand '%s' failed: %s" % (command_name, msg))

        # Collect result elements (those with status attributes or text)
        result = {}
        for elem in root.iter():
            status = elem.get('status')
            if status:
                result[elem.tag] = {'status': status}
        return result

    @staticmethod
    def _check_config_response(xml_string):
        """Verify config write response indicates success (ADR 0004 §7).

        Success: <Configuration><Success/></Configuration>
        """
        root = ET.fromstring(xml_string)

        if root.find('.//Success') is not None:
            return True

        # Check for explicit error elements
        failure = root.find('.//Failure')
        if failure is None:
            failure = root.find('.//Error')
        if failure is not None:
            reason = failure.find('.//Reason')
            msg = reason.text.strip() if reason is not None and reason.text else 'Unknown error'
            raise Exception("Configuration write failed: %s" % msg)

        return True

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
            url_segment = path.replace('.', '/')
            url_path = 'getxml?location=/Configuration/%s' % url_segment
            resp_body = self._request('GET', url_path)
            values = self._extract_leaf_values(resp_body)
            result.update(values)
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
            url_segment = path.replace('.', '/')
            url_path = 'getxml?location=/Status/%s' % url_segment
            resp_body = self._request('GET', url_path)
            values = self._extract_leaf_values(resp_body)
            result.update(values)
        return result
