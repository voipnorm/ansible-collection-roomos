# Copyright: (c) 2026, Chris Norman <voipnorm>
# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve inventory variables before the module argument/environment fallback."""
from ansible.plugins.action import ActionBase


class RoomOSAction(ActionBase):
    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        task_vars = task_vars or {}
        original_task = self._task
        self._task = original_task.copy()
        self._task.args = dict(original_task.args)
        fallbacks = {
            'transport': ('roomos_transport',),
            'device_id': ('roomos_device_id',),
            'token': ('roomos_token',),
            'host': ('roomos_host', 'ansible_host'),
            'username': ('roomos_username', 'ansible_user'),
            'password': ('roomos_password', 'ansible_password'),
            'validate_certs': ('roomos_validate_certs',),
            'timeout': ('roomos_timeout',),
        }
        try:
            for argument, variables in fallbacks.items():
                if argument in self._task.args:
                    continue
                for variable in variables:
                    if variable in task_vars:
                        self._task.args[argument] = self._templar.template(task_vars[variable])
                        break
            result.update(self._execute_module(task_vars=task_vars, tmp=tmp))
            return result
        finally:
            self._task = original_task
