# Compatibility Matrix

## RoomOS versions

| RoomOS Version | Status | Notes |
|---|---|---|
| RoomOS 11.x | ✅ Supported | Primary target |
| RoomOS 26.x | ✅ Supported | |
| CE 9.x | ❌ Not supported | Different API surface, end-of-support |

## Device series

| Series | Example models | Supported |
|---|---|---|
| Room series | Room Kit, Room Kit Pro, Room Kit Mini, Room Bar | ✅ |
| Desk series | Desk, Desk Pro, Desk Mini | ✅ |
| Board series | Board 55, Board 70, Board 85, Board Pro | ✅ |
| Navigator | Room Navigator (as touch controller) | ✅ (limited) |

## Ansible versions

| Version | Status |
|---|---|
| ansible-core >= 2.15 | ✅ Supported |
| ansible-core < 2.15 | ❌ Not tested |

## Python versions

| Version | Status |
|---|---|
| Python >= 3.10 | ✅ Supported |
| Python < 3.10 | ❌ Not supported |

## Transport compatibility

| Transport | Auth method | Use case |
|---|---|---|
| `local` | HTTP Basic (username/password) | On-prem devices with direct IP access |
| `cloud` | Webex Bearer token | Cloud-managed devices, no direct IP needed |
