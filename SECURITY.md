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

- `password`, `token`, `config`, and command `arguments` module arguments are marked `no_log=True`
- Diff output redacts sensitive config paths (passwords, keys, SIP auth, SNMP community)
- Examples always use Ansible Vault or environment variable lookups — never hardcoded credentials

### TLS Certificate Validation

- `validate_certs` defaults to `true` for local and cloud requests.
- Install the local device CA in the controller trust store. Use explicit `false` only for an isolated trusted lab.
- Authenticated redirects are rejected; responses are limited to 8 MiB and command POSTs are never automatically replayed.
- Endpoint error bodies are not echoed because they may contain escaped secrets.
- Whole-dictionary protection can also mask matching ordinary values in returned diffs.
- Endpoint testing is read-only by default; live configuration tests require explicit opt-in.
