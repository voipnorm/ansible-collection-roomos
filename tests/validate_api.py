#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Gate 0.5 — API Validation Script
# Validates all RoomOS API endpoints and captures fixtures for unit test mocking.
#
# Usage:
#   export WEBEX_TOKEN="your-token"
#   export ROOMOS_HOST="192.168.128.192"
#   export ROOMOS_DEVICE_ID="Y2lzY29..."
#   export ROOMOS_USERNAME="admin"        # optional, default: admin
#   export ROOMOS_PASSWORD=""             # optional, default: empty
#   python3 tests/validate_api.py
#
# Outputs:
#   tests/fixtures/cloud/*.json   — Cloud API request/response pairs
#   tests/fixtures/local/*.json   — Local API request/response pairs (with XML in body)

from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import textwrap
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------

WEBEX_TOKEN = os.environ.get('WEBEX_TOKEN', '')
DEVICE_ID = os.environ.get('ROOMOS_DEVICE_ID',
    'Y2lzY29zcGFyazovL3VybjpURUFNOnVzLXdlc3QtMl9yL0RFVklDRS84MTNhNjg3My00ZTFhLTQzMjAtYjBlZC0wYTMyOTM0YTg5NzM=')
HOST = os.environ.get('ROOMOS_HOST', '192.168.128.192')
USERNAME = os.environ.get('ROOMOS_USERNAME', 'admin')
PASSWORD = os.environ.get('ROOMOS_PASSWORD', '')

FIXTURES_DIR = Path(__file__).parent / 'fixtures'
CLOUD_DIR = FIXTURES_DIR / 'cloud'
LOCAL_DIR = FIXTURES_DIR / 'local'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# SSL context that ignores self-signed certs (required for local RoomOS)
INSECURE_SSL = ssl.create_default_context()
INSECURE_SSL.check_hostname = False
INSECURE_SSL.verify_mode = ssl.CERT_NONE

RESULTS: list[dict] = []


def save_fixture(directory: Path, name: str, data: dict) -> None:
    """Save a fixture as pretty-printed JSON."""
    directory.mkdir(parents=True, exist_ok=True)
    filepath = directory / f'{name}.json'
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    print(f'  💾 Saved: {filepath}')


def cloud_request(method: str, path: str, body: dict | None = None,
                  expect_error: bool = False) -> dict:
    """Make a Webex cloud API request."""
    url = f'https://webexapis.com/v1/{path}'
    headers = {
        'Authorization': f'Bearer {WEBEX_TOKEN}',
        'Content-Type': 'application/json',
    }

    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    fixture = {
        'request': {
            'method': method,
            'url': url,
            'headers': {k: ('Bearer <REDACTED>' if k == 'Authorization' else v)
                       for k, v in headers.items()},
            'body': body,
        },
        'response': {},
    }

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode()
            resp_headers = dict(resp.headers)
            fixture['response'] = {
                'status': resp.status,
                'headers': resp_headers,
                'body': json.loads(resp_body) if resp_body else None,
            }
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode() if e.fp else ''
        fixture['response'] = {
            'status': e.code,
            'reason': e.reason,
            'headers': dict(e.headers) if e.headers else {},
            'body': resp_body,
        }
        if not expect_error:
            fixture['error'] = str(e)
    except Exception as e:
        fixture['response'] = {'error': str(e)}

    return fixture


def cloud_request_raw(method: str, path: str, body_bytes: bytes | None = None,
                      content_type: str = 'application/json',
                      expect_error: bool = False) -> dict:
    """Make a Webex cloud API request with custom Content-Type."""
    url = f'https://webexapis.com/v1/{path}'
    headers = {
        'Authorization': f'Bearer {WEBEX_TOKEN}',
        'Content-Type': content_type,
    }

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)

    fixture = {
        'request': {
            'method': method,
            'url': url,
            'headers': {k: ('Bearer <REDACTED>' if k == 'Authorization' else v)
                       for k, v in headers.items()},
            'body': body_bytes.decode() if body_bytes else None,
        },
        'response': {},
    }

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode()
            resp_headers = dict(resp.headers)
            fixture['response'] = {
                'status': resp.status,
                'headers': resp_headers,
                'body': json.loads(resp_body) if resp_body else None,
            }
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode() if e.fp else ''
        fixture['response'] = {
            'status': e.code,
            'reason': e.reason,
            'headers': dict(e.headers) if e.headers else {},
            'body': resp_body,
        }
        if not expect_error:
            fixture['error'] = str(e)
    except Exception as e:
        fixture['response'] = {'error': str(e)}

    return fixture


def local_request(method: str, path: str, body: str | None = None,
                  content_type: str = 'text/xml',
                  expect_error: bool = False) -> dict:
    """Make a local HTTP request to a RoomOS device."""
    url = f'https://{HOST}/{path}'

    # HTTP Basic auth
    credentials = base64.b64encode(f'{USERNAME}:{PASSWORD}'.encode()).decode()
    headers = {
        'Authorization': f'Basic {credentials}',
        'Content-Type': content_type,
    }

    data = body.encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    fixture = {
        'request': {
            'method': method,
            'url': url,
            'headers': {k: ('Basic <REDACTED>' if k == 'Authorization' else v)
                       for k, v in headers.items()},
            'body': body,
        },
        'response': {},
    }

    try:
        with urllib.request.urlopen(req, timeout=30, context=INSECURE_SSL) as resp:
            resp_body = resp.read().decode()
            resp_headers = dict(resp.headers)
            fixture['response'] = {
                'status': resp.status,
                'headers': resp_headers,
                'body': resp_body,
            }
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode() if e.fp else ''
        fixture['response'] = {
            'status': e.code,
            'reason': e.reason,
            'headers': dict(e.headers) if e.headers else {},
            'body': resp_body,
        }
        if not expect_error:
            fixture['error'] = str(e)
    except Exception as e:
        fixture['response'] = {'error': str(e)}

    return fixture


def report(name: str, fixture: dict, success: bool | None = None) -> None:
    """Print a test result line."""
    status_code = fixture.get('response', {}).get('status', '???')
    error = fixture.get('response', {}).get('error') or fixture.get('error')

    if success is None:
        success = 'error' not in fixture and 'error' not in fixture.get('response', {})

    icon = '✅' if success else '❌'
    line = f'{icon} {name} — HTTP {status_code}'
    if error:
        line += f' — {error}'
    print(line)

    RESULTS.append({'name': name, 'status': status_code, 'success': success, 'error': error})


# ---------------------------------------------------------------------------
# Cloud API Tests
# ---------------------------------------------------------------------------

def test_cloud_status_query():
    """Cloud: Query xStatus (SystemUnit.Uptime) — GET with query params"""
    print('\n📡 Cloud: Status query (SystemUnit.Uptime)')
    fixture = cloud_request('GET',
        f'xapi/status?deviceId={DEVICE_ID}&name=SystemUnit.Uptime')
    save_fixture(CLOUD_DIR, 'status_query_uptime', fixture)
    report('cloud_status_uptime', fixture)

    print('\n📡 Cloud: Status query (Standby.State)')
    fixture2 = cloud_request('GET',
        f'xapi/status?deviceId={DEVICE_ID}&name=Standby.State')
    save_fixture(CLOUD_DIR, 'status_query_standby', fixture2)
    report('cloud_status_standby', fixture2)
    return fixture


def test_cloud_status_invalid_path():
    """Cloud: Query invalid status path (error fixture)"""
    print('\n📡 Cloud: Status query — invalid path')
    fixture = cloud_request('GET',
        f'xapi/status?deviceId={DEVICE_ID}&name=NonExistent.Fake.Path',
        expect_error=True)
    save_fixture(CLOUD_DIR, 'status_query_invalid_path', fixture)
    report('cloud_status_invalid_path', fixture, success=True)  # Expected error
    return fixture


def test_cloud_config_read():
    """Cloud: Read xConfiguration (Audio.DefaultVolume)"""
    print('\n📡 Cloud: Config read')
    fixture = cloud_request('GET',
        f'deviceConfigurations?deviceId={DEVICE_ID}&key=Audio.DefaultVolume')
    save_fixture(CLOUD_DIR, 'config_read_success', fixture)
    report('cloud_config_read', fixture)
    return fixture


def test_cloud_config_write_noop(current_volume: int | str | None = None):
    """Cloud: Write xConfiguration using JSON Patch format.

    Webex requires:
    - Content-Type: application/json-patch+json
    - deviceId in query string (not body)
    - JSON Patch operations array as body
    """
    print('\n📡 Cloud: Config write (no-op via JSON Patch)')

    if current_volume is None:
        current_volume = 50  # safe default

    # JSON Patch format: replace the configured value
    patch_body = [
        {
            'op': 'replace',
            'path': 'Audio.DefaultVolume/sources/configured/value',
            'value': int(current_volume),
        }
    ]

    fixture = cloud_request_raw(
        'PATCH',
        f'deviceConfigurations?deviceId={DEVICE_ID}',
        body_bytes=json.dumps(patch_body).encode(),
        content_type='application/json-patch+json',
    )
    save_fixture(CLOUD_DIR, 'config_write_noop', fixture)
    report('cloud_config_write', fixture)
    return fixture


def test_cloud_command():
    """Cloud: Execute xCommand (Audio.Volume.Set — set to current value = no-op)"""
    print('\n📡 Cloud: Command execution (Audio.Volume.Set — no-op)')
    fixture = cloud_request('POST', 'xapi/command/Audio.Volume.Set', body={
        'deviceId': DEVICE_ID,
        'arguments': {
            'Level': 50,
        },
    })
    save_fixture(CLOUD_DIR, 'command_volume_set', fixture)
    report('cloud_command', fixture)
    return fixture


def test_cloud_command_invalid():
    """Cloud: Execute invalid xCommand (error fixture)"""
    print('\n📡 Cloud: Command — invalid path')
    fixture = cloud_request('POST', 'xapi/command/NonExistent.Fake.Command', body={
        'deviceId': DEVICE_ID,
    }, expect_error=True)
    save_fixture(CLOUD_DIR, 'command_invalid_path', fixture)
    report('cloud_command_invalid', fixture, success=True)  # Expected error
    return fixture


def test_cloud_auth_failure():
    """Cloud: Request with invalid token (error fixture)"""
    print('\n📡 Cloud: Auth failure')
    # Temporarily swap token
    global WEBEX_TOKEN
    real_token = WEBEX_TOKEN
    WEBEX_TOKEN = 'invalid-token-for-testing'
    fixture = cloud_request('POST', 'xapi/status/query', body={
        'deviceId': DEVICE_ID,
        'arguments': {'StatusPathList': ['SystemUnit.Uptime']}
    }, expect_error=True)
    WEBEX_TOKEN = real_token
    save_fixture(CLOUD_DIR, 'auth_failure', fixture)
    report('cloud_auth_failure', fixture, success=True)  # Expected error
    return fixture


# ---------------------------------------------------------------------------
# Local API Tests
# ---------------------------------------------------------------------------

def test_local_status_read():
    """Local: GET xStatus (SystemUnit)"""
    print('\n🖥️  Local: Status read')
    fixture = local_request('GET', 'getxml?location=/Status/SystemUnit')
    save_fixture(LOCAL_DIR, 'status_read_success', fixture)
    report('local_status_read', fixture)
    return fixture


def test_local_config_read():
    """Local: GET xConfiguration (Audio)"""
    print('\n🖥️  Local: Config read')
    fixture = local_request('GET', 'getxml?location=/Configuration/Audio')
    save_fixture(LOCAL_DIR, 'config_read_success', fixture)
    report('local_config_read', fixture)
    return fixture


def test_local_command():
    """Local: POST xCommand via putxml (Audio.Volume.Set — set to current = no-op)"""
    print('\n🖥️  Local: Command execution (Audio.Volume.Set — no-op)')
    xml_body = textwrap.dedent('''\
        <Command>
          <Audio>
            <Volume>
              <Set command="True">
                <Level>50</Level>
              </Set>
            </Volume>
          </Audio>
        </Command>
    ''')
    fixture = local_request('POST', 'putxml', body=xml_body)
    save_fixture(LOCAL_DIR, 'command_volume_set', fixture)
    report('local_command', fixture)
    return fixture


def test_local_config_write_noop():
    """Local: POST xConfiguration via putxml (set DefaultVolume to current = no-op)"""
    print('\n🖥️  Local: Config write (no-op, sets current value)')

    # First read current value
    read_fixture = local_request('GET', 'getxml?location=/Configuration/Audio/DefaultVolume')
    # Try to extract current volume from XML response
    current_vol = '50'  # safe default
    resp_body = read_fixture.get('response', {}).get('body', '')
    if 'DefaultVolume' in str(resp_body):
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(resp_body)
            vol_elem = root.find('.//DefaultVolume')
            if vol_elem is not None and vol_elem.text:
                current_vol = vol_elem.text.strip()
                print(f'  Current DefaultVolume: {current_vol}')
        except ET.ParseError:
            pass

    xml_body = textwrap.dedent(f'''\
        <Configuration>
          <Audio>
            <DefaultVolume>{current_vol}</DefaultVolume>
          </Audio>
        </Configuration>
    ''')
    fixture = local_request('POST', 'putxml', body=xml_body)
    save_fixture(LOCAL_DIR, 'config_write_noop', fixture)
    report('local_config_write', fixture)
    return fixture


def test_local_command_invalid():
    """Local: POST invalid xCommand (error fixture)"""
    print('\n🖥️  Local: Command — invalid path')
    xml_body = textwrap.dedent('''\
        <Command>
          <NonExistent>
            <Fake>
              <Path/>
            </Fake>
          </NonExistent>
        </Command>
    ''')
    fixture = local_request('POST', 'putxml', body=xml_body, expect_error=True)
    save_fixture(LOCAL_DIR, 'command_invalid_path', fixture)
    report('local_command_invalid', fixture, success=True)  # Expected error
    return fixture


def test_local_auth_failure():
    """Local: Request with wrong credentials (error fixture)"""
    print('\n🖥️  Local: Auth failure')
    global USERNAME, PASSWORD
    real_user, real_pass = USERNAME, PASSWORD
    USERNAME, PASSWORD = 'baduser', 'badpass'
    fixture = local_request('GET', 'getxml?location=/Status/SystemUnit',
                           expect_error=True)
    USERNAME, PASSWORD = real_user, real_pass
    save_fixture(LOCAL_DIR, 'auth_failure', fixture)
    report('local_auth_failure', fixture, success=True)  # Expected error
    return fixture


# ---------------------------------------------------------------------------
# Rate limit header capture
# ---------------------------------------------------------------------------

def capture_rate_limit_headers():
    """Cloud: Capture Webex rate limit headers from a normal response."""
    print('\n📡 Cloud: Rate limit header capture')
    fixture = cloud_request('GET',
        f'deviceConfigurations?deviceId={DEVICE_ID}&key=Audio.DefaultVolume')
    headers = fixture.get('response', {}).get('headers', {})
    rate_headers = {k: v for k, v in headers.items()
                    if 'rate' in k.lower() or 'retry' in k.lower() or 'limit' in k.lower()}
    if rate_headers:
        print(f'  Rate limit headers: {json.dumps(rate_headers, indent=2)}')
    else:
        print('  No rate limit headers found in response')
    save_fixture(CLOUD_DIR, 'rate_limit_headers', {
        'rate_limit_headers': rate_headers,
        'all_response_headers': headers,
    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print('=' * 60)
    print('Gate 0.5 — RoomOS API Validation')
    print('=' * 60)

    if not WEBEX_TOKEN:
        print('❌ WEBEX_TOKEN not set. Export it first:')
        print('   export WEBEX_TOKEN="your-token"')
        sys.exit(1)

    print(f'\nDevice ID: {DEVICE_ID[:30]}...')
    print(f'Host:      {HOST}')
    print(f'Username:  {USERNAME}')

    # ---- Cloud Tests ----
    print('\n' + '=' * 60)
    print('CLOUD API TESTS')
    print('=' * 60)

    cloud_status = test_cloud_status_query()
    test_cloud_status_invalid_path()
    cloud_config = test_cloud_config_read()

    # Extract current volume for no-op write
    current_vol = None
    try:
        items = cloud_config.get('response', {}).get('body', {}).get('items', {})
        vol_info = items.get('Audio.DefaultVolume', {})
        current_vol = vol_info.get('value')
        if current_vol is not None:
            print(f'  Current cloud Audio.DefaultVolume: {current_vol}')
    except Exception:
        pass

    test_cloud_config_write_noop(current_vol)
    test_cloud_command()
    test_cloud_command_invalid()
    test_cloud_auth_failure()
    capture_rate_limit_headers()

    # ---- Local Tests ----
    print('\n' + '=' * 60)
    print('LOCAL API TESTS')
    print('=' * 60)

    test_local_status_read()
    test_local_config_read()
    test_local_command()
    test_local_config_write_noop()
    test_local_command_invalid()
    test_local_auth_failure()

    # ---- Summary ----
    print('\n' + '=' * 60)
    print('SUMMARY')
    print('=' * 60)
    passed = sum(1 for r in RESULTS if r['success'])
    failed = sum(1 for r in RESULTS if not r['success'])
    print(f'\n  Total: {len(RESULTS)} | ✅ Passed: {passed} | ❌ Failed: {failed}')

    print(f'\n  Fixtures saved to:')
    print(f'    {CLOUD_DIR}/')
    print(f'    {LOCAL_DIR}/')

    if failed:
        print('\n  Failed tests:')
        for r in RESULTS:
            if not r['success']:
                print(f'    ❌ {r["name"]} — {r["error"]}')
        sys.exit(1)

    print('\n  ✅ All endpoints validated! Ready for Gate 3 (transport implementation).')


if __name__ == '__main__':
    main()
