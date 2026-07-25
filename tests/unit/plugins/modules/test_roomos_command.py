# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for roomos_command module."""

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
    command='Audio.Volume.Set',
    arguments={'Level': 50},
    transport='cloud',
    device_id='test-device-id',
    token='test-token',
    validate_certs=False,
    timeout=30,
)

LOCAL_PARAMS = dict(
    command='Audio.Volume.Set',
    arguments={'Level': 50},
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

class TestCommandCloudSuccess:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_command_cloud_success(self, mock_open_url):
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps({
            'deviceId': 'test', 'result': {'VolumeSetResult': {'status': 'OK'}}
        }).encode()
        mock_open_url.return_value = resp

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_command
        exc = _run_module(roomos_command, dict(CLOUD_PARAMS))
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['changed'] is True
        assert 'output' in result


class TestCommandLocalSuccess:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local.open_url')
    def test_command_local_success(self, mock_open_url):
        resp = mock.MagicMock()
        resp.read.return_value = b'<Command><VolumeSetResult status="OK"/></Command>'
        mock_open_url.return_value = resp

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_command
        exc = _run_module(roomos_command, dict(LOCAL_PARAMS))
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['changed'] is True


class TestCommandCheckMode:
    def test_check_mode_no_api_call(self):
        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_command
        exc = _run_module(roomos_command, dict(CLOUD_PARAMS), check_mode=True)
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['changed'] is True
        assert result['would_execute'] is True


class TestCommandInvalidPath:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_command_invalid_path(self, mock_open_url):
        import io
        from urllib.error import HTTPError
        mock_open_url.side_effect = HTTPError(
            url='https://webexapis.com/v1/test', code=400, msg='Bad Request',
            hdrs=mock.MagicMock(),
            fp=io.BytesIO(json.dumps({'message': 'Command not found'}).encode()),
        )
        params = dict(CLOUD_PARAMS)
        params['command'] = 'NonExistent.Command'

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_command
        exc = _run_module(roomos_command, params)
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleFailJson)
        assert 'failed' not in result or result.get('msg')


class TestCommandMissingTransportArgs:
    def test_cloud_missing_token(self):
        params = dict(CLOUD_PARAMS)
        del params['token']

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_command
        exc = _run_module(roomos_command, params)
        assert isinstance(exc.value, AnsibleFailJson)

    def test_local_missing_host(self):
        params = dict(LOCAL_PARAMS)
        del params['host']

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_command
        exc = _run_module(roomos_command, params)
