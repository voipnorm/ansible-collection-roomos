# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Local HTTP XML transport for voipnorm.roomos modules."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.voipnorm.roomos.plugins.module_utils.roomos_common import RoomOSTransport


class LocalTransport(RoomOSTransport):
    """Transport using direct HTTP XML (/putxml, /getxml) to RoomOS devices."""

    def __init__(self, module, host, username, password):
        self.module = module
        self.host = host
        self.username = username
        self.password = password
        self.validate_certs = module.params['validate_certs']
        self.timeout = module.params['timeout']
        self.base_url = 'https://%s' % host

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
