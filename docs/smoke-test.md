# Endpoint smoke test

The automated audit used mocks and a loopback HTTPS endpoint. A real RoomOS or
Webex endpoint was not contacted. Run these checks on a lab device after installing
the candidate collection. Both transports verify certificates by default.

## Install the local candidate

From the repository root, using the prepared `.venv`:

```sh
.venv/bin/ansible-galaxy collection build --force
.venv/bin/ansible-galaxy collection install voipnorm-roomos-0.1.6.tar.gz -p .ansible/collections --force
```

## Read-only local smoke

Set `ROOMOS_HOST`, `ROOMOS_USERNAME`, and `ROOMOS_PASSWORD` in your shell using your
normal secret-management method. Do not put credentials in a command line or
commit them. Trust the device's CA on the controller before testing.

```sh
PYTHONPATH=.ansible/collections .venv/bin/python tests/validate_api.py --transport local
```

Expected: TLS validation enabled, two status reads, one configuration read, zero
writes. For a deliberately isolated self-signed lab endpoint, add
`--insecure-local`; this explicitly disables certificate verification.

## Read-only cloud smoke

Set `ROOMOS_DEVICE_ID` and `ROOMOS_TOKEN` (or `WEBEX_TOKEN`).

```sh
PYTHONPATH=.ansible/collections .venv/bin/python tests/validate_api.py --transport cloud
```

Expected: the same read counts and zero writes. There is no cloud insecure switch.

## Optional local write and restore

Only run this on an idle lab device. The test reads `Audio.DefaultVolume`, writes a
different value, verifies it, restores the exact original value in `finally`, and
verifies restoration. Interrupting the process or losing connectivity can prevent
restoration; record the original value before running so you can recover it.

```sh
ROOMOS_RUN_INTEGRATION=1 ROOMOS_ALLOW_WRITES=1 PYTHONPATH=.ansible/collections \
  .venv/bin/python -m pytest tests/integration -v
```

For an isolated self-signed local lab, also set `ROOMOS_INSECURE_LOCAL=1`.
Cloud write testing is skipped because restoring a configured override requires
preserving its source/provenance. Read-only cloud checks still run when credentials
are provided.

## Actual Ansible playbook

Use `connection: local` and the inventory exported by CE-Deploy. Set its Vault
variables, then run `docs/examples/smoke.yml`:

```sh
ANSIBLE_COLLECTIONS_PATH=.ansible/collections .venv/bin/ansible-playbook \
  -i inventory.yml docs/examples/smoke.yml --ask-vault-pass
```

The action plugins resolve explicit module arguments, then `roomos_*` inventory
variables, standard Ansible connection variables, and finally module environment
fallbacks. `roomos_validate_certs` can supply a deliberate local certificate opt-out.
The playbook requests uptime and software version and asserts they are present.
It makes no configuration writes or commands.
