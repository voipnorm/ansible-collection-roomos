# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for roomos_common utilities."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.voipnorm.roomos.plugins.module_utils.roomos_common import (
    normalize_config_value,
)


class TestNormalizeConfigValue:
    """Tests for the value normalization layer."""

    @pytest.mark.parametrize("value", ["true", "TRUE", "on", "Off", "yes", "no", "1", "0", "001", "  50  "])
    def test_string_values_are_exact(self, value):
        assert normalize_config_value(value) == value

    def test_integer_normalization(self):
        assert normalize_config_value(50) == normalize_config_value("50")

    def test_string_passthrough(self):
        assert normalize_config_value("America/Los_Angeles") == "America/Los_Angeles"

    def test_whitespace_preserved(self):
        assert normalize_config_value("  hello  ") == "  hello  "

    def test_empty_string(self):
        assert normalize_config_value("") == ""
