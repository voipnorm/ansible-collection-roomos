# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for local HTTP XML transport."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

# TODO: Implement after Gate 0.5 (API validation)
# Test list from megaplan:
# - test_local_auth_header — Basic auth credentials correct
# - test_local_auth_missing_host — Fails with clear error
# - test_offline_device — Clear error with device IP
# - test_xml_parse_success — Correct dict output
# - test_xml_parse_error — xAPI error XML -> meaningful message
# - test_response_normalization — Correct TransportResponse shape
# - test_timeout — Request times out, clear error
