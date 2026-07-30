# Changelog

## 0.1.4 (2026-07-30)

### Bug Fixes

- **Cloud transport: type coercion** — Added `_coerce_value()` to convert string config values to native Python types (int, float, bool) before sending to the Webex JSON Patch API. Fixes `HTTP 400: string found, integer expected` errors when setting numeric configs like `Audio.DefaultVolume` via cloud transport.
- **Cloud transport: idempotency** — `get_configuration()` now prefers `sources.configured.value` (updates synchronously after PATCH) over `appliedConfigurationValue` (has eventual consistency). Fixes false `changed=true` on consecutive runs via cloud transport.

## 0.1.3 (2026-07-25)

- Initial pre-release with `roomos_command`, `roomos_config`, `roomos_status` modules
- Local and cloud transport support
- Idempotent config with check mode, diff, and sensitive path redaction
- AnsibleBlocks pack definition
