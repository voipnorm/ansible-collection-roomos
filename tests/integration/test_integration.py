# Copyright: (c) 2026, Chris Norman <voipnorm>
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in real endpoint tests. Writes require a second explicit opt-in."""
import os
from types import SimpleNamespace

import pytest

from ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud import CloudTransport
from ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local import LocalTransport

pytestmark = pytest.mark.skipif(os.environ.get('ROOMOS_RUN_INTEGRATION') != '1',
                                reason='Set ROOMOS_RUN_INTEGRATION=1 for real endpoint access')


@pytest.fixture(params=['local', 'cloud'])
def transport(request):
    params = {'timeout': 30, 'validate_certs': True}
    if request.param == 'cloud':
        token = os.environ.get('ROOMOS_TOKEN') or os.environ.get('WEBEX_TOKEN')
        device_id = os.environ.get('ROOMOS_DEVICE_ID')
        if not token or not device_id:
            pytest.skip('Cloud credentials not set')
        params.update(token=token, device_id=device_id)
        return CloudTransport(SimpleNamespace(params=params))
    host, username, password = (os.environ.get(key) for key in
                                ('ROOMOS_HOST', 'ROOMOS_USERNAME', 'ROOMOS_PASSWORD'))
    if not host or not username or password is None:
        pytest.skip('Local credentials not set')
    params['validate_certs'] = os.environ.get('ROOMOS_INSECURE_LOCAL') != '1'
    return LocalTransport(SimpleNamespace(params=params), host, username, password)


def test_status(transport):
    result = transport.get_status(['SystemUnit.Uptime', 'Standby.State'])
    assert result.get('SystemUnit.Uptime') is not None
    assert result.get('Standby.State') is not None


def test_config_read(transport):
    assert transport.get_configuration(['Audio.DefaultVolume']).get('Audio.DefaultVolume') is not None


@pytest.mark.skipif(os.environ.get('ROOMOS_ALLOW_WRITES') != '1', reason='Writes require ROOMOS_ALLOW_WRITES=1')
def test_config_restore(transport):
    # Cloud defaults may have no configured override: do not change provenance.
    if isinstance(transport, CloudTransport):
        pytest.skip('Cloud write/restore needs configured-source provenance; use local lab test')
    path = 'Audio.DefaultVolume'
    original = transport.get_configuration([path])[path]
    assert original is not None and str(original).isdigit()
    desired = '25' if str(original) != '25' else '35'
    try:
        transport.set_configuration({path: desired})
        assert transport.get_configuration([path])[path] == desired
    finally:
        transport.set_configuration({path: original})
        assert transport.get_configuration([path])[path] == original, 'Endpoint restore failed'
