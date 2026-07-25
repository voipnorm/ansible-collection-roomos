# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for roomos_status module."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Module exit/fail exception helpers
# ---------------------------------------------------------------------------

class AnsibleExitJson(Exception):
    def __init__(self, kwargs):
        self.kwargs = kwargs

class AnsibleFailJson(Exception):
    def __init__(self, kwargs):
        self.kwargs = kwargs


def _run_module(module_cls, params, check_mode=False):
    """Run an Ansible module with mocked exit_json/fail_json."""
    with mock.patch.multiple(
        'ansible.module_utils.basic.AnsibleModule',
        exit_json=mock.MagicMock(side_effect=lambda **kw: (_ for _ in ()).throw(AnsibleExitJson(kw))),
        fail_json=mock.MagicMock(side_effect=lambda **kw: (_ for _ in ()).throw(AnsibleFailJson(kw))),
    ):
        args = {'ANSIBLE_MODULE_ARGS': params}
        if check_mode:
            args['ANSIBLE_MODULE_ARGS']['_ansible_check_mode'] = True

        with mock.patch('ansible.module_utils.basic._ANSIBLE_ARGS',
                       json.dumps(args).encode('utf-8')), \
             mock.patch('ansible.module_utils.basic._ANSIBLE_PROFILE', 'legacy'):
            with pytest.raises((AnsibleExitJson, AnsibleFailJson)) as exc_info:
                module_cls.main()
            return exc_info


CLOUD_PARAMS = dict(
    paths=['SystemUnit.Uptime', 'Standby.State'],
    transport='cloud',
    device_id='test-device-id',
    token='test-token',
    validate_certs=False,
    timeout=30,
)

LOCAL_PARAMS = dict(
    paths=['SystemUnit.Uptime'],
    transport='local',
    host='192.168.1.100',
    username='admin',
    password='pass',
    validate_certs=False,
    timeout=30,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStatusCloudSuccess:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_status_cloud_success(self, mock_open_url):
        mock_open_url.side_effect = [
            mock.MagicMock(read=mock.MagicMock(return_value=json.dumps({
                'deviceId': 'test', 'result': {'SystemUnit': {'Uptime': 61269}}
            }).encode())),
            mock.MagicMock(read=mock.MagicMock(return_value=json.dumps({
                'deviceId': 'test', 'result': {'Standby': {'State': 'Off'}}
            }).encode())),
        ]

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_status
        exc = _run_module(roomos_status, dict(CLOUD_PARAMS))
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['changed'] is False
        assert result['values']['SystemUnit.Uptime'] == 61269
        assert result['values']['Standby.State'] == 'Off'


class TestStatusLocalSuccess:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local.open_url')
    def test_status_local_success(self, mock_open_url):
        resp = mock.MagicMock()
        resp.read.return_value = b'<Status><SystemUnit><Uptime>100</Uptime></SystemUnit></Status>'
        mock_open_url.return_value = resp

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_status
        exc = _run_module(roomos_status, dict(LOCAL_PARAMS))
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['changed'] is False
        assert result['values']['SystemUnit.Uptime'] == '100'


class TestStatusMultiplePaths:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_status_multiple_paths(self, mock_open_url):
        mock_open_url.side_effect = [
            mock.MagicMock(read=mock.MagicMock(return_value=json.dumps({
                'deviceId': 'test', 'result': {'SystemUnit': {'Uptime': 100}}
            }).encode())),
            mock.MagicMock(read=mock.MagicMock(return_value=json.dumps({
                'deviceId': 'test', 'result': {'Standby': {'State': 'Off'}}
            }).encode())),
        ]

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_status
        exc = _run_module(roomos_status, dict(CLOUD_PARAMS))
        result = exc.value.kwargs
        assert len(result['values']) == 2


class TestStatusMissingPathWarn:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_missing_path_warn(self, mock_open_url):
        # Status returns empty result for nonexistent path
        mock_open_url.return_value = mock.MagicMock(
            read=mock.MagicMock(return_value=json.dumps({
                'deviceId': 'test', 'result': {}
            }).encode()))

        params = dict(CLOUD_PARAMS)
        params['paths'] = ['NonExistent.Path']
        params['on_missing'] = 'warn'

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_status
        exc = _run_module(roomos_status, params)
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['values']['NonExistent.Path'] is None


class TestStatusMissingPathFail:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_missing_path_fail(self, mock_open_url):
        mock_open_url.return_value = mock.MagicMock(
            read=mock.MagicMock(return_value=json.dumps({
                'deviceId': 'test', 'result': {}
            }).encode()))

        params = dict(CLOUD_PARAMS)
        params['paths'] = ['NonExistent.Path']
        params['on_missing'] = 'fail'

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_status
        exc = _run_module(roomos_status, params)
        assert isinstance(exc.value, AnsibleFailJson)


class TestStatusMissingPathIgnore:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_missing_path_ignore(self, mock_open_url):
        mock_open_url.return_value = mock.MagicMock(
            read=mock.MagicMock(return_value=json.dumps({
                'deviceId': 'test', 'result': {}
            }).encode()))

        params = dict(CLOUD_PARAMS)
        params['paths'] = ['NonExistent.Path']
        params['on_missing'] = 'ignore'

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_status
        exc = _run_module(roomos_status, params)
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['values']['NonExistent.Path'] is None


class TestStatusCheckMode:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_check_mode_still_reads(self, mock_open_url):
        mock_open_url.return_value = mock.MagicMock(
            read=mock.MagicMock(return_value=json.dumps({
                'deviceId': 'test', 'result': {'SystemUnit': {'Uptime': 99}}
            }).encode()))

        params = dict(CLOUD_PARAMS)
        params['paths'] = ['SystemUnit.Uptime']

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_status
        exc = _run_module(roomos_status, params, check_mode=True)
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['changed'] is False
