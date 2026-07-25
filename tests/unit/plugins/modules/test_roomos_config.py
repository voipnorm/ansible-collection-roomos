# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for roomos_config module."""

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


def _run_module(module_cls, params, check_mode=False, diff=False):
    """Run an Ansible module with mocked exit_json/fail_json."""
    with mock.patch.multiple(
        'ansible.module_utils.basic.AnsibleModule',
        exit_json=mock.MagicMock(side_effect=lambda **kw: (_ for _ in ()).throw(AnsibleExitJson(kw))),
        fail_json=mock.MagicMock(side_effect=lambda **kw: (_ for _ in ()).throw(AnsibleFailJson(kw))),
    ):
        args = {'ANSIBLE_MODULE_ARGS': params}
        if check_mode:
            args['ANSIBLE_MODULE_ARGS']['_ansible_check_mode'] = True
        if diff:
            args['ANSIBLE_MODULE_ARGS']['_ansible_diff'] = True

        with mock.patch('ansible.module_utils.basic._ANSIBLE_ARGS',
                       json.dumps(args).encode('utf-8')), \
             mock.patch('ansible.module_utils.basic._ANSIBLE_PROFILE', 'legacy'):
            with pytest.raises((AnsibleExitJson, AnsibleFailJson)) as exc_info:
                module_cls.main()
            return exc_info


CLOUD_PARAMS = dict(
    config={'Audio.DefaultVolume': 50},
    transport='cloud',
    device_id='test-device-id',
    token='test-token',
    validate_certs=False,
    timeout=30,
)

LOCAL_PARAMS = dict(
    config={'Audio.DefaultVolume': '50'},
    transport='local',
    host='192.168.1.100',
    username='admin',
    password='pass',
    validate_certs=False,
    timeout=30,
)


# ---------------------------------------------------------------------------
# Helper: mock cloud transport responses (get_config then set_config)
# ---------------------------------------------------------------------------

def _cloud_config_responses(current_value, set_response=None):
    """Return side_effect list for cloud config read + write."""
    if set_response is None:
        set_response = {}
    read_resp = mock.MagicMock(read=mock.MagicMock(return_value=json.dumps({
        'items': {
            'Audio.DefaultVolume': {
                'value': current_value,
                'appliedConfigurationValue': {'value': current_value},
            },
        },
    }).encode()))
    write_resp = mock.MagicMock(read=mock.MagicMock(
        return_value=json.dumps(set_response).encode()))
    return [read_resp, write_resp]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestConfigCloudChanged:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_config_cloud_changed(self, mock_open_url):
        mock_open_url.side_effect = _cloud_config_responses(30)

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_config
        exc = _run_module(roomos_config, dict(CLOUD_PARAMS))
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['changed'] is True
        assert 'Audio.DefaultVolume' in result['changed_keys']


class TestConfigLocalChanged:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local.open_url')
    def test_config_local_changed(self, mock_open_url):
        mock_open_url.side_effect = [
            # get_configuration response
            mock.MagicMock(read=mock.MagicMock(
                return_value=b'<Configuration><Audio><DefaultVolume>30</DefaultVolume></Audio></Configuration>')),
            # set_configuration response
            mock.MagicMock(read=mock.MagicMock(
                return_value=b'<Configuration><Success/></Configuration>')),
        ]

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_config
        exc = _run_module(roomos_config, dict(LOCAL_PARAMS))
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['changed'] is True


class TestConfigIdempotent:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_config_idempotent(self, mock_open_url):
        # Current value matches desired — no change
        mock_open_url.return_value = mock.MagicMock(read=mock.MagicMock(
            return_value=json.dumps({
                'items': {
                    'Audio.DefaultVolume': {
                        'value': 50,
                        'appliedConfigurationValue': {'value': 50},
                    },
                },
            }).encode()))

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_config
        exc = _run_module(roomos_config, dict(CLOUD_PARAMS))
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['changed'] is False
        assert result['changed_keys'] == []


class TestConfigCheckMode:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_config_check_mode(self, mock_open_url):
        # Only read response — no write should happen
        mock_open_url.return_value = mock.MagicMock(read=mock.MagicMock(
            return_value=json.dumps({
                'items': {
                    'Audio.DefaultVolume': {
                        'value': 30,
                        'appliedConfigurationValue': {'value': 30},
                    },
                },
            }).encode()))

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_config
        exc = _run_module(roomos_config, dict(CLOUD_PARAMS), check_mode=True)
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['changed'] is True
        # Only one call (read), not two (read + write)
        assert mock_open_url.call_count == 1


class TestConfigDiffOutput:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_config_diff_output(self, mock_open_url):
        mock_open_url.side_effect = _cloud_config_responses(30)

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_config
        exc = _run_module(roomos_config, dict(CLOUD_PARAMS), diff=True)
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['diff']['before']['Audio.DefaultVolume'] == 30
        assert result['diff']['after']['Audio.DefaultVolume'] == 50


class TestConfigSensitiveRedaction:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_config_sensitive_redaction(self, mock_open_url):
        params = dict(CLOUD_PARAMS)
        params['config'] = {'SIP.Authentication.Password': 'newsecret'}

        mock_open_url.side_effect = [
            mock.MagicMock(read=mock.MagicMock(return_value=json.dumps({
                'items': {
                    'SIP.Authentication.Password': {
                        'value': 'oldsecret',
                        'appliedConfigurationValue': {'value': 'oldsecret'},
                    },
                },
            }).encode())),
            mock.MagicMock(read=mock.MagicMock(return_value=json.dumps({}).encode())),
        ]

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_config
        exc = _run_module(roomos_config, params, diff=True)
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['diff']['before']['SIP.Authentication.Password'] == '********'
        assert result['diff']['after']['SIP.Authentication.Password'] == '********'


class TestConfigValueNormalization:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_string_50_equals_int_50(self, mock_open_url):
        params = dict(CLOUD_PARAMS)
        params['config'] = {'Audio.DefaultVolume': '50'}  # string

        mock_open_url.return_value = mock.MagicMock(read=mock.MagicMock(
            return_value=json.dumps({
                'items': {
                    'Audio.DefaultVolume': {
                        'value': 50,  # int
                        'appliedConfigurationValue': {'value': 50},
                    },
                },
            }).encode()))

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_config
        exc = _run_module(roomos_config, params)
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['changed'] is False


class TestConfigPartialChange:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_only_changed_keys_reported(self, mock_open_url):
        params = dict(CLOUD_PARAMS)
        params['config'] = {
            'Audio.DefaultVolume': 50,
            'Time.Zone': 'US/Pacific',
        }

        mock_open_url.side_effect = [
            # get_configuration — volume is same, timezone different
            mock.MagicMock(read=mock.MagicMock(return_value=json.dumps({
                'items': {
                    'Audio.DefaultVolume': {
                        'value': 50,
                        'appliedConfigurationValue': {'value': 50},
                    },
                },
            }).encode())),
            mock.MagicMock(read=mock.MagicMock(return_value=json.dumps({
                'items': {
                    'Time.Zone': {
                        'value': 'US/Eastern',
                        'appliedConfigurationValue': {'value': 'US/Eastern'},
                    },
                },
            }).encode())),
            # set_configuration
            mock.MagicMock(read=mock.MagicMock(return_value=json.dumps({}).encode())),
        ]

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_config
        exc = _run_module(roomos_config, params)
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['changed'] is True
        assert 'Time.Zone' in result['changed_keys']
        assert 'Audio.DefaultVolume' not in result['changed_keys']


class TestConfigFailureModes:
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_failure_mode_fail(self, mock_open_url):
        mock_open_url.side_effect = [
            # read succeeds
            mock.MagicMock(read=mock.MagicMock(return_value=json.dumps({
                'items': {
                    'Audio.DefaultVolume': {
                        'value': 30,
                        'appliedConfigurationValue': {'value': 30},
                    },
                },
            }).encode())),
            # write fails
            Exception("Write failed"),
        ]

        params = dict(CLOUD_PARAMS)
        params['failure_mode'] = 'fail'

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_config
        exc = _run_module(roomos_config, params)
        assert isinstance(exc.value, AnsibleFailJson)

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_failure_mode_warn(self, mock_open_url):
        mock_open_url.side_effect = [
            mock.MagicMock(read=mock.MagicMock(return_value=json.dumps({
                'items': {
                    'Audio.DefaultVolume': {
                        'value': 30,
                        'appliedConfigurationValue': {'value': 30},
                    },
                },
            }).encode())),
            Exception("Write failed"),
        ]

        params = dict(CLOUD_PARAMS)
        params['failure_mode'] = 'warn'

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_config
        exc = _run_module(roomos_config, params)
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['changed'] is True

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_failure_mode_ignore(self, mock_open_url):
        mock_open_url.side_effect = [
            mock.MagicMock(read=mock.MagicMock(return_value=json.dumps({
                'items': {
                    'Audio.DefaultVolume': {
                        'value': 30,
                        'appliedConfigurationValue': {'value': 30},
                    },
                },
            }).encode())),
            Exception("Write failed"),
        ]

        params = dict(CLOUD_PARAMS)
        params['failure_mode'] = 'ignore'

        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_config
        exc = _run_module(roomos_config, params)
        result = exc.value.kwargs
        assert isinstance(exc.value, AnsibleExitJson)
        assert result['changed'] is True
