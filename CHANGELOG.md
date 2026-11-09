# Changelog

## 0.1.6 (unreleased)

- Verify TLS by default, reject redirects, and protect secret-bearing Ansible arguments and errors.
- Fix per-path configuration failure reporting, exact string comparisons, schema-driven cloud typing, indexed paths, and positive response validation.
- Add inventory action plugins, making CE-Deploy inventory and documented fallback behavior work.
- Bound responses/retry waits, close connections, and avoid replaying command POSTs.
- Replace unsafe endpoint tooling with read-only smoke checks and explicit local write/restore tests.
- Fix CI constraints and execution-environment metadata; synchronize the RoomOS pack at 1.1.1 / collection 0.1.6.

## 0.1.5 (2026-09-19)

### Security

- Removed test-device credentials and identifiers from integration-test defaults, documentation comments, and captured fixtures. Integration tooling now requires credentials to be supplied explicitly through environment variables.

## 0.1.4 (2026-07-30)

### Bug Fixes

- **Cloud transport: type coercion** — Added `_coerce_value()` to convert string config values to native Python types (int, float, bool) before sending to the Webex JSON Patch API. Fixes `HTTP 400: string found, integer expected` errors when setting numeric configs like `Audio.DefaultVolume` via cloud transport.
- **Cloud transport: idempotency** — `get_configuration()` now prefers `sources.configured.value` (updates synchronously after PATCH) over `appliedConfigurationValue` (has eventual consistency). Fixes false `changed=true` on consecutive runs via cloud transport.

## 0.1.3 (2026-07-25)

- Initial pre-release with `roomos_command`, `roomos_config`, `roomos_status` modules
- Local and cloud transport support
- Idempotent config with check mode, diff, and sensitive path redaction
- AnsibleBlocks pack definition
