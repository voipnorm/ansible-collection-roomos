# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for cloud transport."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import io
import json
from unittest import mock
from urllib.error import HTTPError, URLError

import pytest

from ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud import CloudTransport


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_module(**overrides):
    """Create a mock AnsibleModule with default cloud params."""
    params = dict(
        transport='cloud',
        device_id='test-device-id',
        token='test-token',
        validate_certs=False,
        timeout=30,
    )
    params.update(overrides)
    m = mock.MagicMock()
    m.params = params
    return m


def _make_response(data, status=200):
    """Create a mock HTTP response."""
    body = json.dumps(data).encode('utf-8')
    resp = mock.MagicMock()
    resp.read.return_value = body
    resp.status = status
    return resp


def _make_http_error(code, body=None, reason='Error'):
    """Create an HTTPError with a readable body."""
    if body is None:
        body = {'message': 'Test error'}
    fp = io.BytesIO(json.dumps(body).encode('utf-8'))
    return HTTPError(
        url='https://webexapis.com/v1/test',
        code=code,
        msg=reason,
        hdrs=mock.MagicMock(),
        fp=fp,
    )


# ---------------------------------------------------------------------------
# Auth / request tests
# ---------------------------------------------------------------------------

class TestCloudAuth:
    """Test authentication header and error handling."""

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_bearer_token_in_header(self, mock_open_url):
        mock_open_url.return_value = _make_response({'result': {}})
        t = CloudTransport(_make_module(token='my-secret-token'))
        t.get_status(['SystemUnit.Uptime'])

        call_kwargs = mock_open_url.call_args
        headers = call_kwargs.kwargs.get('headers') or call_kwargs[1].get('headers')
        assert headers['Authorization'] == 'Bearer my-secret-token'

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_device_id_in_url(self, mock_open_url):
        mock_open_url.return_value = _make_response({'result': {}})
        t = CloudTransport(_make_module(device_id='my-device'))
        t.get_status(['SystemUnit.Uptime'])

        call_args = mock_open_url.call_args
        url = call_args[0][0] if call_args[0] else call_args.kwargs.get('url', '')
        assert 'deviceId=my-device' in url


# ---------------------------------------------------------------------------
# Retry tests
# ---------------------------------------------------------------------------

class TestCloudRetry:
    """Test retry logic on 429/5xx."""

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.time.sleep')
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_retry_on_429(self, mock_open_url, mock_sleep):
        err = _make_http_error(429)
        mock_open_url.side_effect = [
            err,
            _make_response({'result': {'SystemUnit': {'Uptime': 100}}}),
        ]
        t = CloudTransport(_make_module())
        result = t.get_status(['SystemUnit.Uptime'])

        assert result == {'SystemUnit.Uptime': 100}
        assert mock_sleep.call_count == 1

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.time.sleep')
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_retry_on_500(self, mock_open_url, mock_sleep):
        err = _make_http_error(500)
        mock_open_url.side_effect = [
            err,
            _make_response({'result': {}}),
        ]
        t = CloudTransport(_make_module())
        t.get_status(['Test.Path'])
        assert mock_sleep.call_count == 1

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_no_retry_on_400(self, mock_open_url):
        mock_open_url.side_effect = _make_http_error(400, {'message': 'Bad request'})
        t = CloudTransport(_make_module())
        with pytest.raises(Exception, match='Bad request'):
            t.execute_command('Invalid.Command')

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_no_retry_on_401(self, mock_open_url):
        mock_open_url.side_effect = _make_http_error(401, {'message': 'Unauthorized'})
        t = CloudTransport(_make_module())
        with pytest.raises(Exception, match='HTTP 401'):
            t.get_status(['SystemUnit.Uptime'])

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_connection_error(self, mock_open_url):
        mock_open_url.side_effect = URLError('Connection refused')
        t = CloudTransport(_make_module())
        with pytest.raises(Exception, match='Cannot connect'):
            t.get_status(['SystemUnit.Uptime'])


# ---------------------------------------------------------------------------
# Status tests
# ---------------------------------------------------------------------------

class TestCloudStatus:
    """Test get_status with real fixture response format."""

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_status_returns_flattened_values(self, mock_open_url):
        mock_open_url.return_value = _make_response({
            'deviceId': 'test',
            'result': {'SystemUnit': {'Uptime': 61269}},
        })
        t = CloudTransport(_make_module())
        result = t.get_status(['SystemUnit.Uptime'])
        assert result == {'SystemUnit.Uptime': 61269}

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_status_empty_result_for_invalid_path(self, mock_open_url):
        mock_open_url.return_value = _make_response({
            'deviceId': 'test',
            'result': {},
        })
        t = CloudTransport(_make_module())
        result = t.get_status(['NonExistent.Path'])
        assert result == {}

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_status_multiple_paths(self, mock_open_url):
        mock_open_url.side_effect = [
            _make_response({'deviceId': 'test', 'result': {'SystemUnit': {'Uptime': 100}}}),
            _make_response({'deviceId': 'test', 'result': {'Standby': {'State': 'Off'}}}),
        ]
        t = CloudTransport(_make_module())
        result = t.get_status(['SystemUnit.Uptime', 'Standby.State'])
        assert result == {'SystemUnit.Uptime': 100, 'Standby.State': 'Off'}


# ---------------------------------------------------------------------------
# Command tests
# ---------------------------------------------------------------------------

class TestCloudCommand:
    """Test execute_command."""

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_command_success(self, mock_open_url):
        mock_open_url.return_value = _make_response({
            'deviceId': 'test',
            'result': {},
        })
        t = CloudTransport(_make_module())
        result = t.execute_command('Audio.Volume.Set', {'Level': 50})
        assert result == {}

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_command_sends_arguments(self, mock_open_url):
        mock_open_url.return_value = _make_response({'deviceId': 'test', 'result': {}})
        t = CloudTransport(_make_module())
        t.execute_command('Audio.Volume.Set', {'Level': 50})

        call_kwargs = mock_open_url.call_args
        sent_data = json.loads(call_kwargs.kwargs.get('data') or call_kwargs[1].get('data', '{}'))
        assert sent_data['arguments'] == {'Level': 50}
        assert sent_data['deviceId'] == 'test-device-id'


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestCloudConfig:
    """Test get_configuration and set_configuration."""

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_config_read_uses_applied_value(self, mock_open_url):
        mock_open_url.return_value = _make_response({
            'deviceId': 'test',
            'items': {
                'Audio.DefaultVolume': {
                    'value': 50,
                    'source': 'default',
                    'appliedConfigurationValue': {'value': 50},
                },
            },
        })
        t = CloudTransport(_make_module())
        result = t.get_configuration(['Audio.DefaultVolume'])
        assert result == {'Audio.DefaultVolume': 50}

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_config_read_falls_back_to_value(self, mock_open_url):
        mock_open_url.return_value = _make_response({
            'deviceId': 'test',
            'items': {
                'Audio.DefaultVolume': {
                    'value': 50,
                },
            },
        })
        t = CloudTransport(_make_module())
        result = t.get_configuration(['Audio.DefaultVolume'])
        assert result == {'Audio.DefaultVolume': 50}

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url')
    def test_config_write_uses_json_patch(self, mock_open_url):
        mock_open_url.return_value = _make_response({})
        t = CloudTransport(_make_module())
        t.set_configuration({'Audio.DefaultVolume': 50})

        call_kwargs = mock_open_url.call_args
        headers = call_kwargs.kwargs.get('headers') or call_kwargs[1].get('headers')
        assert headers['Content-Type'] == 'application/json-patch+json'

        sent_data = json.loads(call_kwargs.kwargs.get('data') or call_kwargs[1].get('data', '[]'))
        assert sent_data[0]['op'] == 'replace'
        assert sent_data[0]['path'] == 'Audio.DefaultVolume/sources/configured/value'
        assert sent_data[0]['value'] == 50


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------

class TestFlattenDict:
    """Test the _flatten_dict helper."""

    def test_simple_flatten(self):
        result = {}
        CloudTransport._flatten_dict({'A': {'B': 1}}, result)
        assert result == {'A.B': 1}

    def test_deep_flatten(self):
        result = {}
        CloudTransport._flatten_dict({'A': {'B': {'C': 'val'}}}, result)
        assert result == {'A.B.C': 'val'}

    def test_multiple_keys(self):
        result = {}
        CloudTransport._flatten_dict({'A': 1, 'B': {'C': 2}}, result)
        assert result == {'A': 1, 'B.C': 2}
