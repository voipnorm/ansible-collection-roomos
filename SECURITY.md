# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 0.x.x | ✅ (current development) |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email the maintainer directly or use [GitHub Security Advisories](https://github.com/voipnorm/ansible-collection-roomos/security/advisories/new)
3. Include a description of the vulnerability and steps to reproduce

We will acknowledge receipt within 48 hours and provide a timeline for a fix.

## Security Considerations

### Credential Handling

- `password` and `token` module arguments are marked `no_log=True`
- Diff output redacts sensitive config paths (passwords, keys, SIP auth, SNMP community)
- Examples always use Ansible Vault or environment variable lookups — never hardcoded credentials

### TLS Certificate Validation

- `validate_certs` defaults to `false` because most RoomOS devices use self-signed certificates
- In production with CA-signed certificates, set `validate_certs: true`
- An ansible-lint rule warns when `validate_certs: false` is used
