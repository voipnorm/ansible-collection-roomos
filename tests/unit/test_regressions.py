"""Behavioral regression coverage for the security and defect audit."""
import contextlib
import io
import json
from unittest import mock
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

import pytest
from ansible.module_utils import basic

from ansible_collections.voipnorm.roomos.plugins.module_utils.roomos_common import (
    ROOMOS_COMMON_ARGS, cloud_path, is_sensitive_path, validate_host, validate_path,
)
from ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud import CloudTransport
from ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local import LocalTransport
from ansible_collections.voipnorm.roomos.plugins.modules import roomos_command, roomos_config
from tests.unit.plugins.module_utils.test_transport_cloud import _make_module, _make_response
from tests.unit.plugins.modules.test_roomos_config import _run_module, CLOUD_PARAMS, AnsibleExitJson, AnsibleFailJson


def test_tls_default():
    assert ROOMOS_COMMON_ARGS['validate_certs']['default'] is True


@pytest.mark.parametrize('transport_cls', [CloudTransport, LocalTransport])
@pytest.mark.parametrize('verified', [True, False])
def test_request_controls(transport_cls, verified):
    module = _make_module(validate_certs=verified)
    t = transport_cls(module) if transport_cls is CloudTransport else transport_cls(module, 'device.example', 'u', 'p')
    name = transport_cls.__module__ + '.open_url'
    with mock.patch(name, return_value=_make_response({'result': {}})) as url:
        t._request('GET', 'https://webexapis.com/v1/test' if transport_cls is CloudTransport else 'getxml')
    assert url.call_args.kwargs['validate_certs'] is verified
    assert url.call_args.kwargs['follow_redirects'] == 'none'
    assert url.call_args.kwargs['use_netrc'] is False
    assert url.call_args.kwargs['unredirected_headers'] == ['Authorization']
    url.return_value.close.assert_called_once()


@pytest.mark.parametrize('module_cls,params', [
    (roomos_config, {'config': {'SIP.Authentication.Password': 'new<&secret'}, '_ansible_diff': True}),
    (roomos_command, {'command': 'UserManagement.User.Add', 'arguments': {'Password': 'new<&secret'}}),
])
def test_real_ansible_output_redacts_secrets(module_cls, params):
    params = dict(params, transport='cloud', token='transport-secret', device_id='dummy')
    fake = mock.MagicMock()
    fake.get_configuration.return_value = {'SIP.Authentication.Password': 'old<&secret'}
    fake.prepare_configuration_value.side_effect = lambda path, value: value
    fake.execute_command.return_value = {'Password': 'new<&secret'}
    output = io.StringIO()
    with mock.patch.object(basic, '_ANSIBLE_ARGS', json.dumps({'ANSIBLE_MODULE_ARGS': params}).encode()), \
         mock.patch.object(basic, '_ANSIBLE_PROFILE', 'legacy', create=True), \
         mock.patch.object(module_cls, 'get_transport', return_value=fake), \
         contextlib.redirect_stdout(output), pytest.raises(SystemExit):
        module_cls.main()
    result = output.getvalue()
    for secret in ('new<&secret', 'old<&secret', 'transport-secret'):
        assert secret not in result
    assert json.loads(result)['changed'] is True


@pytest.mark.parametrize('value', ['001', 'On', 'off', '  password  ', '1.0'])
def test_cloud_string_values_not_guessed(value):
    assert CloudTransport._coerce_value(value) == value
    assert CloudTransport._coerce_value(value, 'string') == value


def test_cloud_metadata_types():
    assert CloudTransport._coerce_value('50', 'integer') == 50
    assert CloudTransport._coerce_value('On', 'boolean') is True
    with pytest.raises(ValueError):
        CloudTransport._coerce_value('nan', 'number')


def test_encoded_device_id():
    t = CloudTransport(_make_module(device_id='id&key=evil+#'))
    with mock.patch(t.__module__ + '.open_url', return_value=_make_response({'result': {}})) as url:
        t.get_status(['SystemUnit.Uptime'])
    query = parse_qs(urlsplit(url.call_args.args[0]).query)
    assert query == {'deviceId': ['id&key=evil+#'], 'name': ['SystemUnit.Uptime']}


@pytest.mark.parametrize('bad', ['Audio..Volume', 'A/<B>', 'A&deviceId=x', '', 'A.0.Value'])
def test_bad_paths(bad):
    with pytest.raises(ValueError):
        validate_path(bad)


@pytest.mark.parametrize('bad', ['example.com/path', 'user:pass@example.com', 'https://example.com', 'example.com?x=1'])
def test_bad_hosts(bad):
    with pytest.raises(ValueError):
        validate_host(bad)


def test_indexed_configuration_xml():
    xml = LocalTransport._build_config_xml({'Network.1.IPv4.Address': '1', 'Network[2].IPv4.Address': '2'})
    root = ET.fromstring(xml)
    assert [node.get('item') for node in root] == ['1', '2']
    assert cloud_path('Network.1.IPv4.Address') == 'Network[1].IPv4.Address'
    assert LocalTransport._extract_leaf_values(xml) == {'Network.1.IPv4.Address': '1', 'Network.2.IPv4.Address': '2'}


def test_empty_and_whitespace_config():
    assert LocalTransport._extract_leaf_values('<Configuration><A><B/></A><C>  secret  </C></Configuration>') == {
        'A.B': '', 'C': '  secret  '}


@pytest.mark.parametrize('xml', ['<Configuration/>', '<html/>', '<Configuration><Success/><Failure/></Configuration>'])
def test_config_requires_unambiguous_success(xml):
    with pytest.raises((ValueError, Exception)):
        LocalTransport._check_config_response(xml)


def test_command_requires_success():
    with pytest.raises(ValueError):
        LocalTransport._check_command_response('<Command><Result/></Command>', 'A.B')


def test_no_command_retry():
    t = CloudTransport(_make_module())
    with mock.patch(t.__module__ + '.open_url', side_effect=HTTPError('https://x', 503, 'bad', {}, None)) as url:
        with pytest.raises(Exception):
            t.execute_command('A.B')
    assert url.call_count == 1


@pytest.mark.parametrize('header,delay', [('999999', 30), ('-10', 0), ('invalid', 1)])
def test_retry_after_bounded(header, delay):
    t = CloudTransport(_make_module())
    with mock.patch(t.__module__ + '.open_url', side_effect=[
        HTTPError('https://x', 429, 'bad', {'Retry-After': header}, None), _make_response({'result': {}})
    ]), mock.patch(t.__module__ + '.time.sleep') as sleep:
        t.get_status(['SystemUnit.Uptime'])
    sleep.assert_called_once_with(delay)


def test_partial_writes_and_failed_keys():
    fake = mock.MagicMock()
    fake.get_configuration.side_effect = [{'Audio.DefaultVolume': 30}, {'Time.Zone': 'old'}]
    fake.prepare_configuration_value.side_effect = lambda path, value: value
    fake.set_configuration.side_effect = [None, ValueError('secret error')]
    params = dict(CLOUD_PARAMS, config={'Audio.DefaultVolume': 50, 'Time.Zone': 'new'}, failure_mode='warn')
    with mock.patch.object(roomos_config, 'get_transport', return_value=fake):
        result = _run_module(roomos_config, params, diff=True).value.kwargs
    assert result['changed_keys'] == ['Audio.DefaultVolume']
    assert result['failed_keys'] == ['Time.Zone']
    assert result['diff']['after'] == {'Audio.DefaultVolume': 50}


def test_missing_config_not_written():
    fake = mock.MagicMock()
    fake.get_configuration.return_value = {}
    with mock.patch.object(roomos_config, 'get_transport', return_value=fake):
        exc = _run_module(roomos_config, dict(CLOUD_PARAMS))
    assert isinstance(exc.value, AnsibleFailJson)
    fake.set_configuration.assert_not_called()


def test_secret_path_aliases():
    for path in ['SIP.Authentication.Password', 'sip.authentication.password', 'SIP[1].Authentication.Password', 'NetworkServices.SNMP.CommunityName']:
        assert is_sensitive_path(path)


def test_empty_config_no_change():
    with mock.patch.object(roomos_config, 'get_transport') as transport:
        exc = _run_module(roomos_config, dict(CLOUD_PARAMS, config={}))
    assert isinstance(exc.value, AnsibleExitJson)
    assert exc.value.kwargs['changed'] is False
    transport.return_value.get_configuration.assert_not_called()


def test_cloud_number_idempotency():
    params = dict(CLOUD_PARAMS, config={'Audio.DefaultVolume': '50'})
    response = _make_response({'items': {'Audio.DefaultVolume': {
        'value': 50, 'valueSpace': {'type': 'number'}}}})
    with mock.patch('ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud.open_url', return_value=response) as url:
        result = _run_module(roomos_config, params).value.kwargs
    assert result['changed'] is False
    assert url.call_count == 1


def test_cloud_status_bracket_alias():
    t = CloudTransport(_make_module())
    response = _make_response({'result': {'Network': [{'IPv4': {'Address': '192.0.2.1'}}]}})
    with mock.patch(t.__module__ + '.open_url', return_value=response):
        assert t.get_status(['Network[1].IPv4.Address'])['Network[1].IPv4.Address'] == '192.0.2.1'


def test_cloud_command_error_result():
    t = CloudTransport(_make_module())
    with mock.patch(t.__module__ + '.open_url', return_value=_make_response({'result': {'status': 'Error'}})):
        with pytest.raises(ValueError, match='error status'):
            t.execute_command('A.B')


def test_local_command_retains_fields():
    result = LocalTransport._check_command_response('<Command><Result status="OK"><CallId>3</CallId></Result></Command>', 'A.B')
    assert result['Result'] == {'status': 'OK', 'CallId': '3'}
