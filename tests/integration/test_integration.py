#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Gate 7 — Integration tests against real RoomOS devices.
#
# These tests hit real hardware/cloud endpoints and are NOT part of CI by default.
# Run manually or via the nightly-integration workflow.
#
# Usage (local transport):
#   export ROOMOS_HOST="192.168.128.192"
#   export ROOMOS_USERNAME="christno"
#   export ROOMOS_PASSWORD="Giantnorm012!"
#   pytest tests/integration/ -v -k local
#
# Usage (cloud transport):
#   export WEBEX_TOKEN="your-webex-token"
#   export ROOMOS_DEVICE_ID="Y2lzY29..."
#   pytest tests/integration/ -v -k cloud
#
# Usage (all):
#   export all of the above
#   pytest tests/integration/ -v

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Environment-based credentials
# ---------------------------------------------------------------------------

WEBEX_TOKEN = os.environ.get('WEBEX_TOKEN', '')
DEVICE_ID = os.environ.get('ROOMOS_DEVICE_ID',
    'Y2lzY29zcGFyazovL3VybjpURUFNOnVzLXdlc3QtMl9yL0RFVklDRS84MTNhNjg3My00ZTFhLTQzMjAtYjBlZC0wYTMyOTM0YTg5NzM=')
HOST = os.environ.get('ROOMOS_HOST', '192.168.128.192')
USERNAME = os.environ.get('ROOMOS_USERNAME', 'christno')
PASSWORD = os.environ.get('ROOMOS_PASSWORD', 'Giantnorm012!')

# ---------------------------------------------------------------------------
# Skip conditions
# ---------------------------------------------------------------------------

skip_no_local = pytest.mark.skipif(
    not HOST or not USERNAME or not PASSWORD,
    reason='Local transport credentials not set (ROOMOS_HOST, ROOMOS_USERNAME, ROOMOS_PASSWORD)')

skip_no_cloud = pytest.mark.skipif(
    not WEBEX_TOKEN or not DEVICE_ID,
    reason='Cloud transport credentials not set (WEBEX_TOKEN, ROOMOS_DEVICE_ID)')

# ---------------------------------------------------------------------------
# Helpers — run modules via subprocess to avoid import-path gymnastics
# ---------------------------------------------------------------------------

from unittest import mock

# We need the Ansible module test harness
sys.path.insert(0, '/tmp/roomos-test')


class AnsibleExitJson(Exception):
    def __init__(self, kwargs):
        self.kwargs = kwargs


class AnsibleFailJson(Exception):
    def __init__(self, kwargs):
        self.kwargs = kwargs


def _run_module(module_cls, params, check_mode=False):
    """Run an Ansible module with real transport (no mocking)."""
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


LOCAL_PARAMS = dict(
    transport='local',
    host=HOST,
    username=USERNAME,
    password=PASSWORD,
    validate_certs=False,
    timeout=30,
)

CLOUD_PARAMS = dict(
    transport='cloud',
    device_id=DEVICE_ID,
    token=WEBEX_TOKEN,
    validate_certs=True,
    timeout=30,
)


# ===========================================================================
# Local transport integration tests
# ===========================================================================

@skip_no_local
class TestLocalStatusQuery:
    """test_status_real_query — Real status paths return real values."""

    def test_local_status_query(self):
        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_status

        params = dict(
            paths=['SystemUnit.Uptime', 'Standby.State'],
            on_missing='warn',
            **LOCAL_PARAMS,
        )
        exc = _run_module(roomos_status, params)
        result = exc.value.kwargs
        assert 'values' in result
        # Uptime should be a number (string of digits)
        uptime = result['values'].get('SystemUnit.Uptime')
        assert uptime is not None, "SystemUnit.Uptime should be present"
        print("Uptime: %s seconds" % uptime)


@skip_no_local
class TestLocalCommandVolumeSetRestore:
    """test_command_volume_set_restore — Set volume, verify, restore."""

    def test_volume_set_restore(self):
        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_config
        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_status

        # 1. Read current volume
        status_params = dict(
            paths=['Audio.Volume'],
            on_missing='fail',
            **LOCAL_PARAMS,
        )
        exc = _run_module(roomos_status, status_params)
        original_volume = exc.value.kwargs['values'].get('Audio.Volume')
        print("Original volume: %s" % original_volume)

        # 2. Set test volume (different from original)
        test_volume = '25' if str(original_volume) != '25' else '35'
        config_params = dict(
            config={'Audio.DefaultVolume': test_volume},
            failure_mode='fail',
            **LOCAL_PARAMS,
        )
        exc = _run_module(roomos_config, config_params)
        result = exc.value.kwargs
        assert result.get('changed') is True, "Should have changed volume"
        print("Set volume to: %s" % test_volume)

        # 3. Run again — should be idempotent
        exc = _run_module(roomos_config, config_params)
        result = exc.value.kwargs
        assert result.get('changed') is False, "Second run should be idempotent"
        print("Idempotency verified")

        # 4. Restore original volume
        restore_params = dict(
            config={'Audio.DefaultVolume': str(original_volume) if original_volume else '50'},
            failure_mode='fail',
            **LOCAL_PARAMS,
        )
        exc = _run_module(roomos_config, restore_params)
        print("Restored volume to: %s" % (original_volume or '50'))


@skip_no_local
class TestLocalConfigIdempotent:
    """test_config_real_idempotent — Set config, run again, changed=false."""

    def test_config_idempotent(self):
        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_config

        # Use a safe, non-disruptive config path
        config_params = dict(
            config={'Time.Zone': 'America/Los_Angeles'},
            failure_mode='fail',
            **LOCAL_PARAMS,
        )
        # First run — may or may not change
        exc = _run_module(roomos_config, config_params)
        first_result = exc.value.kwargs
        print("First run changed: %s" % first_result.get('changed'))

        # Second run — must be idempotent
        exc = _run_module(roomos_config, config_params)
        second_result = exc.value.kwargs
        assert second_result.get('changed') is False, \
            "Second run should report changed=false (idempotent)"
        print("Idempotency confirmed")


@skip_no_local
class TestLocalConfigDiff:
    """test_config_real_diff — Diff output matches actual change."""

    def test_config_diff(self):
        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_config

        config_params = dict(
            config={'Audio.DefaultVolume': '42'},
            failure_mode='fail',
            _ansible_diff=True,
            **LOCAL_PARAMS,
        )
        exc = _run_module(roomos_config, config_params)
        result = exc.value.kwargs

        if result.get('changed'):
            diff = result.get('diff')
            assert diff is not None, "Diff should be present when changed=True and diff mode on"
            assert 'before' in diff
            assert 'after' in diff
            assert 'Audio.DefaultVolume' in diff['after']
            print("Diff: %s -> %s" % (diff['before'], diff['after']))
        else:
            print("Already at target value, no diff generated")

        # Restore
        restore = dict(
            config={'Audio.DefaultVolume': '50'},
            failure_mode='fail',
            **LOCAL_PARAMS,
        )
        _run_module(roomos_config, restore)


# ===========================================================================
# Cloud transport integration tests
# ===========================================================================

@skip_no_cloud
class TestCloudStatusQuery:
    """test_cloud_real_status — Cloud API returns real status values."""

    def test_cloud_status_query(self):
        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_status

        params = dict(
            paths=['SystemUnit.Uptime', 'Standby.State', 'SystemUnit.Software.Version'],
            on_missing='warn',
            **CLOUD_PARAMS,
        )
        exc = _run_module(roomos_status, params)
        result = exc.value.kwargs
        assert 'values' in result
        assert result.get('changed') is False

        version = result['values'].get('SystemUnit.Software.Version')
        uptime = result['values'].get('SystemUnit.Uptime')
        print("Cloud — Version: %s, Uptime: %s" % (version, uptime))
        assert version is not None, "Version should be present via cloud"


@skip_no_cloud
class TestCloudCommandStandbyQuery:
    """test_command_standby_query — xCommand via cloud (non-disruptive)."""

    def test_standby_status_query(self):
        from ansible_collections.voipnorm.roomos.plugins.modules import roomos_status

        # Query standby state — this is read-only and non-disruptive
        params = dict(
            paths=['Standby.State'],
            on_missing='warn',
            **CLOUD_PARAMS,
        )
        exc = _run_module(roomos_status, params)
        result = exc.value.kwargs
        state = result['values'].get('Standby.State')
        assert state in ('Off', 'Standby', 'EnteringStandby', 'Halfwake', None), \
            "Unexpected standby state: %s" % state
        print("Cloud standby state: %s" % state)
