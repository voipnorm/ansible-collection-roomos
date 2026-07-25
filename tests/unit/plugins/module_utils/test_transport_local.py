# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for local HTTP XML transport."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest import mock
from urllib.error import HTTPError, URLError

import pytest

from ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local import LocalTransport


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_module(**overrides):
    """Create a mock AnsibleModule with default local params."""
    params = dict(
        transport='local',
        host='192.168.1.100',
        username='admin',
        password='password',
        validate_certs=False,
        timeout=30,
    )
    params.update(overrides)
    m = mock.MagicMock()
    m.params = params
    return m


def _make_transport(**overrides):
    """Create a LocalTransport with default params."""
    module = _make_module(**overrides)
    return LocalTransport(
        module,
        host=module.params['host'],
        username=module.params['username'],
        password=module.params['password'],
    )


def _make_response(xml_body):
    """Create a mock HTTP response with XML body."""
    resp = mock.MagicMock()
    resp.read.return_value = xml_body.encode('utf-8')
    return resp


# ---------------------------------------------------------------------------
# XML builder tests
# ---------------------------------------------------------------------------

class TestBuildCommandXml:
    """Test _build_command_xml static method."""

    def test_simple_command(self):
        xml = LocalTransport._build_command_xml('SystemUnit.Boot')
        assert '<SystemUnit>' in xml
        assert '<Boot command="True"' in xml
        assert '<Command>' in xml

    def test_command_with_arguments(self):
        xml = LocalTransport._build_command_xml('Audio.Volume.Set', {'Level': '50'})
        assert '<Set command="True"' in xml
        assert '<Level>50</Level>' in xml

    def test_command_true_on_last_element(self):
        xml = LocalTransport._build_command_xml('A.B.C')
        assert 'command="True"' in xml
        # Only the last element should have the command attribute
        assert xml.count('command="True"') == 1


class TestBuildConfigXml:
    """Test _build_config_xml static method."""

    def test_single_path(self):
        xml = LocalTransport._build_config_xml({'Audio.DefaultVolume': '50'})
        assert '<Configuration>' in xml
        assert '<Audio>' in xml
        assert '<DefaultVolume>50</DefaultVolume>' in xml

    def test_shared_parent(self):
        xml = LocalTransport._build_config_xml({
            'Audio.DefaultVolume': '50',
            'Audio.SoundsAndAlerts.RingVolume': '60',
        })
        # Audio element should appear once (shared parent)
        assert xml.count('<Audio>') == 1


# ---------------------------------------------------------------------------
# XML parser tests
# ---------------------------------------------------------------------------

class TestExtractLeafValues:
    """Test _extract_leaf_values static method."""

    def test_simple_status(self):
        xml = '''<?xml version="1.0"?>
        <Status>
          <SystemUnit>
            <Uptime>61269</Uptime>
          </SystemUnit>
        </Status>'''
        result = LocalTransport._extract_leaf_values(xml)
        assert result == {'SystemUnit.Uptime': '61269'}

    def test_config_value(self):
        xml = '''<?xml version="1.0"?>
        <Configuration>
          <Audio>
            <DefaultVolume>50</DefaultVolume>
          </Audio>
        </Configuration>'''
        result = LocalTransport._extract_leaf_values(xml)
        assert result == {'Audio.DefaultVolume': '50'}

    def test_indexed_items(self):
        xml = '''<?xml version="1.0"?>
        <Status>
          <Network item="1">
            <IPv4>
              <Address>10.0.0.1</Address>
            </IPv4>
          </Network>
        </Status>'''
        result = LocalTransport._extract_leaf_values(xml)
        assert result == {'Network.1.IPv4.Address': '10.0.0.1'}

    def test_multiple_leaves(self):
        xml = '''<?xml version="1.0"?>
        <Status>
          <SystemUnit>
            <Uptime>100</Uptime>
            <ProductId>Room Bar</ProductId>
          </SystemUnit>
        </Status>'''
        result = LocalTransport._extract_leaf_values(xml)
        assert result['SystemUnit.Uptime'] == '100'
        assert result['SystemUnit.ProductId'] == 'Room Bar'


# ---------------------------------------------------------------------------
# Command response parser tests
# ---------------------------------------------------------------------------

class TestCheckCommandResponse:
    """Test _check_command_response static method."""

    def test_success_response(self):
        xml = '<?xml version="1.0"?>\n<Command>\n<VolumeSetResult status="OK"/>\n</Command>'
        result = LocalTransport._check_command_response(xml, 'Audio.Volume.Set')
        assert result['VolumeSetResult']['status'] == 'OK'

    def test_action_error(self):
        xml = '''<?xml version="1.0"?>
        <Command>
          <ActionError>
            <Reason>No action detected in document</Reason>
          </ActionError>
        </Command>'''
        with pytest.raises(Exception, match='No action detected'):
            LocalTransport._check_command_response(xml, 'Bad.Command')

    def test_status_error(self):
        xml = '''<?xml version="1.0"?>
        <Command>
          <SomeResult status="Error">
            <Reason>Unknown command</Reason>
          </SomeResult>
        </Command>'''
        with pytest.raises(Exception, match='Unknown command'):
            LocalTransport._check_command_response(xml, 'Bad.Command')


# ---------------------------------------------------------------------------
# Config response parser tests
# ---------------------------------------------------------------------------

class TestCheckConfigResponse:
    """Test _check_config_response static method."""

    def test_success_response(self):
        xml = '<?xml version="1.0"?>\n<Configuration>\n  <Success/>\n</Configuration>'
        assert LocalTransport._check_config_response(xml) is True

    def test_failure_response(self):
        xml = '''<?xml version="1.0"?>
        <Configuration>
          <Failure>
            <Reason>Invalid path</Reason>
          </Failure>
        </Configuration>'''
        with pytest.raises(Exception, match='Invalid path'):
            LocalTransport._check_config_response(xml)


# ---------------------------------------------------------------------------
# Auth / connection tests
# ---------------------------------------------------------------------------

class TestLocalAuth:
    """Test authentication and connection error handling."""

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local.open_url')
    def test_basic_auth_params(self, mock_open_url):
        mock_open_url.return_value = _make_response(
            '<Status><SystemUnit><Uptime>100</Uptime></SystemUnit></Status>')
        t = _make_transport(username='myuser', password='mypass')
        t.get_status(['SystemUnit.Uptime'])

        call_kwargs = mock_open_url.call_args
        assert call_kwargs.kwargs.get('url_username') == 'myuser' or \
               call_kwargs[1].get('url_username') == 'myuser'
        assert call_kwargs.kwargs.get('force_basic_auth') is True or \
               call_kwargs[1].get('force_basic_auth') is True

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local.open_url')
    def test_auth_failure_401(self, mock_open_url):
        mock_open_url.side_effect = HTTPError(
            url='https://192.168.1.100/getxml',
            code=401,
            msg='Unauthorized',
            hdrs=mock.MagicMock(),
            fp=None,
        )
        t = _make_transport()
        with pytest.raises(Exception, match='Authentication failed'):
            t.get_status(['SystemUnit.Uptime'])

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local.open_url')
    def test_connection_error(self, mock_open_url):
        mock_open_url.side_effect = URLError('Connection refused')
        t = _make_transport()
        with pytest.raises(Exception, match='Cannot connect'):
            t.get_status(['SystemUnit.Uptime'])


# ---------------------------------------------------------------------------
# Retry tests
# ---------------------------------------------------------------------------

class TestLocalRetry:
    """Test retry logic on 5xx."""

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local.time.sleep')
    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local.open_url')
    def test_retry_on_500(self, mock_open_url, mock_sleep):
        mock_open_url.side_effect = [
            HTTPError('https://test', 500, 'Error', mock.MagicMock(), None),
            _make_response('<Status><SystemUnit><Uptime>1</Uptime></SystemUnit></Status>'),
        ]
        t = _make_transport()
        result = t.get_status(['SystemUnit.Uptime'])
        assert result == {'SystemUnit.Uptime': '1'}
        assert mock_sleep.call_count == 1


# ---------------------------------------------------------------------------
# Integration-style tests (full transport methods)
# ---------------------------------------------------------------------------

class TestLocalTransportMethods:
    """Test full transport methods with mocked HTTP."""

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local.open_url')
    def test_get_status(self, mock_open_url):
        mock_open_url.return_value = _make_response(
            '<Status><SystemUnit><Uptime>61269</Uptime></SystemUnit></Status>')
        t = _make_transport()
        result = t.get_status(['SystemUnit.Uptime'])
        assert result == {'SystemUnit.Uptime': '61269'}

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local.open_url')
    def test_get_configuration(self, mock_open_url):
        mock_open_url.return_value = _make_response(
            '<Configuration><Audio><DefaultVolume>50</DefaultVolume></Audio></Configuration>')
        t = _make_transport()
        result = t.get_configuration(['Audio.DefaultVolume'])
        assert result == {'Audio.DefaultVolume': '50'}

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local.open_url')
    def test_execute_command(self, mock_open_url):
        mock_open_url.return_value = _make_response(
            '<Command><VolumeSetResult status="OK"/></Command>')
        t = _make_transport()
        result = t.execute_command('Audio.Volume.Set', {'Level': 50})
        assert result['VolumeSetResult']['status'] == 'OK'

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local.open_url')
    def test_set_configuration(self, mock_open_url):
        mock_open_url.return_value = _make_response(
            '<Configuration><Success/></Configuration>')
        t = _make_transport()
        result = t.set_configuration({'Audio.DefaultVolume': '50'})
        assert result == {'success': True}

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local.open_url')
    def test_execute_command_url(self, mock_open_url):
        mock_open_url.return_value = _make_response(
            '<Command><VolumeSetResult status="OK"/></Command>')
        t = _make_transport()
        t.execute_command('Audio.Volume.Set', {'Level': 50})

        call_args = mock_open_url.call_args
        url = call_args[0][0] if call_args[0] else call_args.kwargs.get('url', '')
        assert url.endswith('/putxml')

    @mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local.open_url')
    def test_get_status_url(self, mock_open_url):
        mock_open_url.return_value = _make_response(
            '<Status><SystemUnit><Uptime>1</Uptime></SystemUnit></Status>')
        t = _make_transport()
        t.get_status(['SystemUnit.Uptime'])

        call_args = mock_open_url.call_args
        url = call_args[0][0] if call_args[0] else call_args.kwargs.get('url', '')
        assert 'getxml?location=/Status/SystemUnit/Uptime' in url
