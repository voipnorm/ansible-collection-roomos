# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Webex Cloud xAPI transport for voipnorm.roomos modules."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.voipnorm.roomos.plugins.module_utils.roomos_common import RoomOSTransport


class CloudTransport(RoomOSTransport):
    """Transport using Webex REST API (webexapis.com/v1/xapi/*)."""

    BASE_URL = 'https://webexapis.com/v1'

    def __init__(self, module):
        self.module = module
        self.device_id = module.params['device_id']
        self.token = module.params['token']
        self.validate_certs = module.params['validate_certs']
        self.timeout = module.params['timeout']

    def execute_command(self, command_name, arguments=None):
        # TODO: Implement after Gate 0.5 API validation
        raise NotImplementedError

    def get_configuration(self, paths):
        # TODO: Implement after Gate 0.5 API validation
        raise NotImplementedError

    def set_configuration(self, config):
        # TODO: Implement after Gate 0.5 API validation
        raise NotImplementedError

    def get_status(self, paths):
        # TODO: Implement after Gate 0.5 API validation
        raise NotImplementedError
