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

    @pytest.mark.parametrize("input_val,expected", [
        ("True", "True"),
        ("true", "True"),
        ("TRUE", "True"),
        ("on", "True"),
        ("On", "True"),
        ("yes", "True"),
        ("1", "True"),
        ("False", "False"),
        ("false", "False"),
        ("FALSE", "False"),
        ("off", "False"),
        ("Off", "False"),
        ("no", "False"),
        ("0", "False"),
    ])
    def test_boolean_normalization(self, input_val, expected):
        assert normalize_config_value(input_val) == expected

    @pytest.mark.parametrize("input_val,expected", [
        ("50", "50"),
        (50, "50"),
        ("  50  ", "50"),
    ])
    def test_integer_normalization(self, input_val, expected):
        assert normalize_config_value(input_val) == expected

    def test_string_passthrough(self):
        assert normalize_config_value("America/Los_Angeles") == "America/Los_Angeles"

    def test_whitespace_trim(self):
        assert normalize_config_value("  hello  ") == "hello"

    def test_empty_string(self):
        assert normalize_config_value("") == ""
