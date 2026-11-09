# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Norman <voipnorm>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Shared pytest fixtures for voipnorm.roomos unit tests."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

# Shared fixtures will be added as transport tests are implemented.
# Examples: mock_module, mock_cloud_transport, mock_local_transport

# Direct pytest runs need the same namespace layout as ansible-test.
import atexit
from pathlib import Path
import sys
import tempfile

_collection_namespace = tempfile.TemporaryDirectory(prefix='roomos-unit-')
_collection_parent = Path(_collection_namespace.name) / 'ansible_collections' / 'voipnorm'
_collection_parent.mkdir(parents=True)
(_collection_parent / 'roomos').symlink_to(Path(__file__).resolve().parents[2], target_is_directory=True)
sys.path.insert(0, _collection_namespace.name)
atexit.register(_collection_namespace.cleanup)
