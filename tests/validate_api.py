# Copyright: (c) 2026, Chris Norman <voipnorm>
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only endpoint smoke test using the installed collection.

Credentials come from ROOMOS_* (or WEBEX_TOKEN for cloud). This script never
writes endpoint configuration or captures raw endpoint data into the repository.
"""
from __future__ import annotations

import argparse
import os
from types import SimpleNamespace

from ansible_collections.voipnorm.roomos.plugins.module_utils.transport_cloud import CloudTransport
from ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local import LocalTransport


def make_transport(transport, insecure_local=False):
    params = {'validate_certs': True, 'timeout': 30}
    if transport == 'cloud':
        params.update(device_id=os.environ.get('ROOMOS_DEVICE_ID'),
                      token=os.environ.get('ROOMOS_TOKEN') or os.environ.get('WEBEX_TOKEN'))
        if not params['device_id'] or not params['token']:
            raise ValueError('Set ROOMOS_DEVICE_ID and ROOMOS_TOKEN (or WEBEX_TOKEN)')
        return CloudTransport(SimpleNamespace(params=params))
    params['validate_certs'] = not insecure_local
    host, user, password = (os.environ.get(key) for key in
                            ('ROOMOS_HOST', 'ROOMOS_USERNAME', 'ROOMOS_PASSWORD'))
    if not host or not user or password is None:
        raise ValueError('Set ROOMOS_HOST, ROOMOS_USERNAME and ROOMOS_PASSWORD')
    return LocalTransport(SimpleNamespace(params=params), host, user, password)


def smoke_test(transport):
    paths = ['SystemUnit.Uptime', 'SystemUnit.Software.Version']
    status = transport.get_status(paths)
    if any(status.get(path) in (None, '') for path in paths):
        raise ValueError('Required status values are missing')
    config = transport.get_configuration(['Audio.DefaultVolume'])
    if config.get('Audio.DefaultVolume') is None:
        raise ValueError('Audio.DefaultVolume is unavailable')
    return {'status_reads': len(paths), 'configuration_reads': 1, 'writes': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transport', choices=['local', 'cloud'], required=True)
    parser.add_argument('--insecure-local', action='store_true',
                        help='Explicit lab-only opt-out for a self-signed local device')
    args = parser.parse_args()
    if args.insecure_local and args.transport != 'local':
        parser.error('--insecure-local is only valid for local devices')
    print('TLS validation: %s' % ('disabled (explicit local opt-out)' if args.insecure_local else 'enabled'))
    try:
        result = smoke_test(make_transport(args.transport, args.insecure_local))
    except Exception:
        parser.exit(1, 'Smoke test failed; check credentials, certificate trust and endpoint diagnostics.\n')
    print('PASS: %(status_reads)d status reads, %(configuration_reads)d config read, %(writes)d writes' % result)


if __name__ == '__main__':
    main()
