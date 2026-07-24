# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for cloud transport."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

# TODO: Implement after Gate 0.5 (API validation)
# Test list from megaplan:
# - test_cloud_auth_header — Bearer token in Authorization header
# - test_cloud_auth_missing_token — Fails with clear error
# - test_retry_on_429 — Retries with backoff
# - test_retry_on_500 — Retries with backoff
# - test_no_retry_on_400 — Fails immediately
# - test_response_normalization — Correct TransportResponse shape
