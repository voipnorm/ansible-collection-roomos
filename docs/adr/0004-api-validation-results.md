# ADR 0004: API Validation Results (Gate 0.5)

- **Status**: Accepted
- **Date**: 2026-07-24
- **Device**: Cisco Room Bar, RoomOS 26.7.1.12 (ce26.7.1.12.67c6e508983)

## Context

Before implementing transport code, we validated all API assumptions against real
endpoints using a Webex sandbox device. This ADR documents the findings and
corrections to our original API assumptions.

## Validation Results

**14/14 endpoints validated successfully** across both cloud and local transports.

### Cloud API (Webex REST)

| Endpoint | Method | Status | Notes |
|---|---|---|---|
| `/v1/xapi/status?deviceId=...&name=...` | GET | ✅ 200 | **Corrected**: GET with query params, not POST |
| `/v1/xapi/status?name=InvalidPath` | GET | ✅ 200 | Returns `{"result": {}}` — no error, empty result |
| `/v1/deviceConfigurations?deviceId=...&key=...` | GET | ✅ 200 | As expected |
| `/v1/deviceConfigurations?deviceId=...` | PATCH | ✅ 200 | **Corrected**: JSON Patch format required |
| `/v1/xapi/command/{commandKey}` | POST | ✅ 200 | **Corrected**: `Audio.Volume.Get` is not a command |
| `/v1/xapi/command/InvalidCommand` | POST | ✅ 400 | Returns structured error JSON |
| Auth with invalid token | Any | ✅ 401 | Standard 401 response |

### Local API (HTTP XML)

| Endpoint | Method | Status | Notes |
|---|---|---|---|
| `/getxml?location=/Status/SystemUnit` | GET | ✅ 200 | Returns XML, `text/xml; charset=UTF-8` |
| `/getxml?location=/Configuration/Audio` | GET | ✅ 200 | Returns XML config tree |
| `/putxml` (xCommand XML) | POST | ✅ 200 | Command requires `command="True"` attribute |
| `/putxml` (xConfiguration XML) | POST | ✅ 200 | Returns `<Success/>` on success |
| `/putxml` (invalid command) | POST | ✅ 200 | Returns 200 with error in XML body |
| Auth with wrong credentials | Any | ✅ 401 | Standard 401 response |

## Key Findings

### 1. Cloud Status API — GET, not POST

**Original assumption**: `POST /v1/xapi/status/query` with JSON body
**Reality**: `GET /v1/xapi/status?deviceId={id}&name={statusPath}`

- Status is a GET with query parameters
- Each status path is queried individually (one `name` per request)
- Response format: `{"deviceId": "...", "result": {"SystemUnit": {"Uptime": 61269}}}`
- Values are returned as native types (integers, not strings)

### 2. Cloud Status — Invalid paths return 200 with empty result

**Original assumption**: Invalid status paths would return 404 or error
**Reality**: Returns HTTP 200 with `{"result": {}}`

**Impact**: `roomos_status` module must check for empty `result` dict to detect
missing paths, not rely on HTTP error codes. The `on_missing` parameter behavior
needs to inspect the result payload.

### 3. Cloud Config Write — JSON Patch format

**Original assumption**: `PATCH` with `{"deviceId": "...", "items": [...]}`
**Reality**: JSON Patch (RFC 6902) format required

- `Content-Type: application/json-patch+json` (not `application/json`)
- `deviceId` goes in query string: `?deviceId={id}`
- Body is a JSON Patch operations array:
  ```json
  [{"op": "replace", "path": "Audio.DefaultVolume/sources/configured/value", "value": 50}]
  ```
- Response is the full device configuration (can be very large, ~987KB)

### 4. Cloud Config Read — Rich metadata

Config read returns rich metadata beyond just the value:
```json
{
  "value": 50,
  "source": "default",
  "sources": {
    "default": {"value": 50, "editability": {"isEditable": false, "reason": "FACTORY_DEFAULT"}},
    "configured": {"value": null, "editability": {"isEditable": true}}
  },
  "valueSpace": {"type": "integer", "maximum": 100, "minimum": 0},
  "appliedConfigurationValue": {"value": 50, "updatedAt": "2026-07-24T19:45:37Z"}
}
```

**Impact**: For idempotency, compare against `appliedConfigurationValue.value` (the
effective value) rather than `sources.configured.value` (which may be null if using default).

### 5. Cloud Command — `Audio.Volume.Get` does not exist

**Original assumption**: `Audio.Volume.Get` is a valid xCommand
**Reality**: Not a command. Volume is queried via xStatus, not xCommand.

- Used `Audio.Volume.Set` with `Level: 50` (current value) for non-disruptive testing
- Command response on success: `{"deviceId": "...", "result": {}}`

### 6. Local Command XML — requires `command="True"` attribute

```xml
<Command>
  <Audio>
    <Volume>
      <Set command="True">
        <Level>50</Level>
      </Set>
    </Volume>
  </Audio>
</Command>
```

Without `command="True"`, the device returns `"No action detected in document"`.

**Response on success**: `<Command><VolumeSetResult status="OK"/></Command>`

### 7. Local Config Write — Success response

```xml
<Configuration>
  <Success/>
</Configuration>
```

Simple `<Success/>` element indicates success. No detailed response body.

### 8. Local Error Handling — HTTP 200 with error in body

Invalid commands return HTTP 200, not 4xx. Error detection must parse the XML body:
- Command errors: check for absence of `status="OK"` or presence of error elements
- The transport layer must inspect response bodies, not just HTTP status codes

### 9. Rate Limiting — No headers observed

No `X-RateLimit-*`, `Retry-After`, or similar headers were present in normal responses.
Rate limiting likely applies but headers may only appear when limits are approached.
Transport implementation should handle 429 responses defensively.

### 10. Device Information Captured

- **Product**: Cisco Room Bar
- **Platform**: Room Bar
- **Software**: RoomOS 26.7.1.12 (ce26.7.1.12.67c6e508983)
- **API Version**: 4
- **Local server**: nginx with strict CSP headers

## Consequences

### Transport Implementation Changes

1. **Cloud status**: Use `GET` with query params, handle empty `result` dict
2. **Cloud config write**: Use JSON Patch format with `application/json-patch+json`
3. **Cloud config read**: Extract `appliedConfigurationValue.value` for idempotency
4. **Local commands**: Always include `command="True"` attribute on action elements
5. **Local errors**: Parse XML body for success/failure, don't rely on HTTP status
6. **Status on_missing**: Check `result` emptiness, not HTTP error codes

### Fixtures Captured

All 14 request/response pairs saved to `tests/fixtures/` for unit test mocking:
- `tests/fixtures/cloud/` — 9 fixtures (success, error, auth failure, rate limit headers)
- `tests/fixtures/local/` — 7 fixtures (success, error, auth failure)
