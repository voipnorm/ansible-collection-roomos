# ADR 0002: Transport Strategy — Cloud API + Local HTTP XML

## Status

Accepted

## Context

Cisco RoomOS devices can be managed via multiple protocols:
1. **Local HTTP XML** — `https://<host>/putxml` and `/getxml` endpoints
2. **Webex Cloud REST API** — `https://webexapis.com/v1/xapi/*` endpoints
3. **SSH/CLI** — Direct SSH to device shell
4. **WebSocket** — xAPI event streaming

We need to decide which transports to support in v1.

## Decision

**Support local HTTP XML and Webex Cloud REST API. Defer SSH and WebSocket.**

### Local HTTP XML

| Operation | Endpoint | Method |
|---|---|---|
| Execute xCommand | `https://<host>/putxml` | POST (XML `<Command>` body) |
| Set xConfiguration | `https://<host>/putxml` | POST (XML `<Configuration>` body) |
| Get xConfiguration | `https://<host>/getxml?location=/Configuration/...` | GET |
| Get xStatus | `https://<host>/getxml?location=/Status/...` | GET |

Auth: HTTP Basic (username/password)

### Webex Cloud REST API

| Operation | Endpoint | Method |
|---|---|---|
| Execute xCommand | `webexapis.com/v1/xapi/command/{commandName}` | POST |
| Set xConfiguration | `webexapis.com/v1/deviceConfigurations` | PATCH |
| Get xConfiguration | `webexapis.com/v1/deviceConfigurations?deviceId=...` | GET |
| Get xStatus | `webexapis.com/v1/xapi/status/query` | POST |

Auth: Bearer token (Webex API token)

## Rationale

- **HTTP XML**: Stateless, fits Ansible's task-by-task model, no extra dependencies
- **Cloud API**: Standard, well-documented, required for cloud-managed devices without direct IP access
- **SSH deferred**: No structured responses — would require complex output parsing
- **WebSocket deferred**: Event streaming doesn't fit Ansible's task model

## Consequences

- Both transports implement the same `RoomOSTransport` interface
- Users select transport via the `transport` parameter (`local` or `cloud`)
- Responses are normalized into a common internal format regardless of transport

## RoomOS Version Support

- RoomOS 11.x: Supported
- RoomOS 26.x: Supported
- CE 9.x: Out of scope (different API surface, end-of-support)
