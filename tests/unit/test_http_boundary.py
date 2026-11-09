"""Exercise TLS, redirects and inventory fallback over real loopback HTTPS."""
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from ansible_collections.voipnorm.roomos.plugins.module_utils.roomos_common import read_response
from ansible_collections.voipnorm.roomos.plugins.module_utils.transport_local import LocalTransport


@pytest.fixture
def endpoint(tmp_path, monkeypatch):
    # Avoid macOS SystemConfiguration proxy lookup in forked pytest workers.
    monkeypatch.setenv("no_proxy", "*")
    cert, key = tmp_path / 'cert.pem', tmp_path / 'key.pem'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                    '-keyout', str(key), '-out', str(cert), '-subj', '/CN=localhost'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    state = {'volume': '30', 'target_requests': 0, 'posts': 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format_string, *args):
            pass

        def do_GET(self):
            if self.path == '/redirect':
                self.send_response(302)
                self.send_header('Location', '/target')
                self.end_headers()
                return
            if self.path == '/target':
                state['target_requests'] += 1
            self.send_response(200)
            self.end_headers()
            self.wfile.write(('<Configuration><Audio><DefaultVolume>%s</DefaultVolume></Audio></Configuration>'
                              % state['volume']).encode())

        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            state['posts'] += 1
            import xml.etree.ElementTree as ET
            state['volume'] = ET.fromstring(body).find('.//DefaultVolume').text
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'<Configuration><Success/></Configuration>')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield '127.0.0.1:%s' % server.server_port, state
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def test_self_signed_tls_rejected_unless_explicit_opt_out(endpoint):
    host, state = endpoint
    module = SimpleNamespace(params={'validate_certs': True, 'timeout': 2})
    t = LocalTransport(module, host, 'audit-user', 'audit-password')
    with pytest.raises(Exception, match='Cannot connect'):
        t.get_configuration(['Audio.DefaultVolume'])
    assert state['posts'] == 0
    module.params['validate_certs'] = False
    t = LocalTransport(module, host, 'audit-user', 'audit-password')
    assert t.get_configuration(['Audio.DefaultVolume']) == {'Audio.DefaultVolume': '30'}
    with pytest.raises(Exception, match='HTTP 302'):
        t._request('GET', 'redirect')
    assert state['target_requests'] == 0


def test_inventory_action_plugin_with_real_ansible(endpoint, tmp_path):
    host, state = endpoint
    collection_root = Path(__file__).resolve().parents[2]
    inventory = tmp_path / 'inventory.json'
    inventory.write_text(json.dumps({'all': {'hosts': {'device': {
        'ansible_host': host, 'roomos_username': 'audit-user', 'roomos_password': 'audit-password',
        'roomos_validate_certs': False, 'ansible_connection': 'local',
        'ansible_python_interpreter': sys.executable}}}}))
    playbook = tmp_path / 'playbook.yml'
    playbook.write_text('''---
- name: Loopback inventory contract
  hosts: device
  gather_facts: false
  tasks:
    - name: Set volume
      voipnorm.roomos.roomos_config:
        config:
          Audio.DefaultVolume: '50'
      register: first
    - name: Repeat volume
      voipnorm.roomos.roomos_config:
        config:
          Audio.DefaultVolume: '50'
      register: second
    - name: Check results
      ansible.builtin.assert:
        that:
          - first.changed
          - not second.changed
''')
    collections = tmp_path / 'collections' / 'ansible_collections' / 'voipnorm'
    collections.mkdir(parents=True)
    (collections / 'roomos').symlink_to(collection_root, target_is_directory=True)
    env = dict(os.environ, ANSIBLE_HOME=str(tmp_path / 'ansible-home'),
               ANSIBLE_COLLECTIONS_PATH=str(tmp_path / 'collections'), ANSIBLE_LOCAL_TEMP=str(tmp_path / 'ansible-tmp'))
    process = subprocess.run([sys.executable, '-m', 'ansible.cli.playbook', '-i', str(inventory),
                              str(playbook), '-vvv'], env=env, capture_output=True, text=True, timeout=60, check=False)
    assert process.returncode == 0, process.stdout + process.stderr
    assert 'audit-password' not in process.stdout + process.stderr
    assert state['volume'] == '50'
    assert state['posts'] == 1


def test_oversize_response_closed():
    class Response:
        closed = False

        def read(self, limit):
            return b'x' * limit

        def close(self):
            self.closed = True

    response = Response()
    with pytest.raises(ValueError, match='8 MiB'):
        read_response(response)
    assert response.closed
